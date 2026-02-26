module;

#include <cstring>
#include <filesystem>
#include <fstream>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
#include <expat.h>

export module senda.compiler.arxml;

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;
import senda.domains;

export namespace senda
{

class ArxmlCompiler : public rupa::compiler::Compiler {
public:
    explicit ArxmlCompiler(const senda::domains::AutosarSchema& schema)
        : schema_(schema) {}

    std::span<const std::string_view> extensions() const override {
        return exts_;
    }

    rupa::compiler::CompileResult compile(
        const std::filesystem::path& path,
        rupa::compiler::CompileContext& context) override
    {
        rupa::compiler::Diagnostics diags;

        // Read file content
        std::ifstream file(path, std::ios::binary | std::ios::ate);
        if (!file) {
            diags.add({rupa::compiler::Severity::Error,
                       "cannot open file: " + path.string(),
                       {path.string(), 0, 0}});
            return rupa::compiler::CompileResult(
                fir::Fir{}, rupa::compiler::DomainExtensions{}, std::move(diags));
        }
        auto size = file.tellg();
        file.seekg(0);
        std::string content(static_cast<size_t>(size), '\0');
        file.read(content.data(), size);

        // Create expat parser
        XML_Parser parser = XML_ParserCreate(nullptr);
        if (!parser) {
            diags.add({rupa::compiler::Severity::Error,
                       "failed to create XML parser",
                       {path.string(), 0, 0}});
            return rupa::compiler::CompileResult(
                fir::Fir{}, rupa::compiler::DomainExtensions{}, std::move(diags));
        }

        // Set up parse state
        fir::Fir fir;
        rupa::fir_builder::FirBuilder builder(fir);

        (void)context;

        ParseState state{
            .schema = schema_,
            .builder = builder,
            .diags = diags,
            .file_path = path.string(),
            .stack = {},
        };

        XML_SetUserData(parser, &state);
        XML_SetElementHandler(parser, on_start_element, on_end_element);
        XML_SetCharacterDataHandler(parser, on_characters);

        // Parse
        if (XML_Parse(parser, content.data(), static_cast<int>(content.size()), XML_TRUE)
            == XML_STATUS_ERROR) {
            diags.add({rupa::compiler::Severity::Error,
                       std::string("XML parse error: ")
                           + XML_ErrorString(XML_GetErrorCode(parser))
                           + " at line "
                           + std::to_string(XML_GetCurrentLineNumber(parser)),
                       {path.string(),
                         static_cast<uint32_t>(XML_GetCurrentLineNumber(parser)), 0}});
        }

        XML_ParserFree(parser);

        return rupa::compiler::CompileResult(
            std::move(fir), rupa::compiler::DomainExtensions{}, std::move(diags));
    }

private:
    static constexpr std::string_view exts_arr_[] = {".arxml"};
    std::span<const std::string_view> exts_{exts_arr_};
    const senda::domains::AutosarSchema& schema_;

    // --- SAX state machine ---

    enum class FrameKind { Object, Property, Skip };

    struct Frame {
        FrameKind kind;
        // Object frame
        rupa::fir_builder::ObjectHandle obj{};
        const senda::domains::TypeInfo* type_info = nullptr;
        // Property frame
        rupa::domain::RoleHandle role{};
        rupa::fir_builder::ObjectHandle parent_obj{};
        std::string text;
        bool is_identity = false;  // true for SHORT-NAME capture
        // Skip frame
        int skip_depth = 0;
    };

    struct ParseState {
        const senda::domains::AutosarSchema& schema;
        rupa::fir_builder::FirBuilder& builder;
        rupa::compiler::Diagnostics& diags;
        std::string file_path;
        std::vector<Frame> stack;
    };

    static void XMLCALL on_start_element(void* user_data, const XML_Char* name,
                                          const XML_Char** /*attrs*/) {
        auto& state = *static_cast<ParseState*>(user_data);
        std::string_view tag(name);

        // Strip namespace prefix if present (e.g., "AR:AUTOSAR" -> "AUTOSAR")
        if (auto pos = tag.find(':'); pos != std::string_view::npos) {
            tag = tag.substr(pos + 1);
        }

        // If top of stack is Skip, increment depth
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Skip) {
            state.stack.back().skip_depth++;
            return;
        }

        // Try type lookup
        auto* type_info = state.schema.tag_to_type.find(tag);
        if (type_info) {
            // Known type element — create object
            Frame frame{};
            frame.kind = FrameKind::Object;
            frame.type_info = type_info;
            // Identity will be set when we see SHORT-NAME
            frame.obj = {};  // deferred
            state.stack.push_back(std::move(frame));
            return;
        }

        // If we're inside an Object frame, check for SHORT-NAME or role lookup
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Object) {
            auto& parent = state.stack.back();

            // SHORT-NAME provides the identity for the parent object
            if (tag == "SHORT-NAME" && !parent.obj.valid()) {
                Frame frame{};
                frame.kind = FrameKind::Property;
                frame.is_identity = true;
                state.stack.push_back(std::move(frame));
                return;
            }

            if (parent.type_info) {
                auto* role = parent.type_info->roles.find(tag);
                if (role) {
                    Frame frame{};
                    frame.kind = FrameKind::Property;
                    frame.role = *role;
                    frame.parent_obj = parent.obj;
                    state.stack.push_back(std::move(frame));
                    return;
                }
            }
        }

        // If we're inside a Property frame, try type lookup (contained object)
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Property) {
            auto* nested_type_info = state.schema.tag_to_type.find(tag);
            if (nested_type_info) {
                Frame frame{};
                frame.kind = FrameKind::Object;
                frame.type_info = nested_type_info;
                frame.obj = {};
                state.stack.push_back(std::move(frame));
                return;
            }
        }

        // Unknown element — skip
        Frame frame{};
        frame.kind = FrameKind::Skip;
        frame.skip_depth = 1;
        state.stack.push_back(std::move(frame));
    }

    static void XMLCALL on_end_element(void* user_data, const XML_Char* /*name*/) {
        auto& state = *static_cast<ParseState*>(user_data);

        if (state.stack.empty()) return;

        auto& frame = state.stack.back();

        switch (frame.kind) {
        case FrameKind::Skip:
            if (--frame.skip_depth > 0) return;
            break;

        case FrameKind::Property:
            if (frame.is_identity && !frame.text.empty()) {
                // SHORT-NAME captured — create the parent object
                if (state.stack.size() >= 2) {
                    auto& parent = state.stack[state.stack.size() - 2];
                    if (parent.kind == FrameKind::Object && parent.type_info
                        && !parent.obj.valid()) {
                        parent.obj = state.builder.begin_object(
                            std::string_view(frame.text),
                            rupa::fir_builder::TypeHandle{parent.type_info->handle.id});
                    }
                }
            } else if (!frame.text.empty() && frame.parent_obj.valid()) {
                // Regular property — add to parent object
                state.builder.add_property(
                    frame.parent_obj, rupa::fir_builder::RoleHandle{frame.role.id},
                    std::string_view(frame.text));
            }
            break;

        case FrameKind::Object:
            // Object finalization is implicit (FirBuilder tracks current object)
            break;
        }

        state.stack.pop_back();
    }

    static void XMLCALL on_characters(void* user_data, const XML_Char* s, int len) {
        auto& state = *static_cast<ParseState*>(user_data);

        if (state.stack.empty()) return;

        auto& frame = state.stack.back();
        if (frame.kind == FrameKind::Property) {
            frame.text.append(s, static_cast<size_t>(len));
        }
    }
};

}  // namespace senda
