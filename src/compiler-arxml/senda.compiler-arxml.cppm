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
import senda.domains.r23_11;

export namespace senda
{

class ArxmlCompiler : public rupa::compiler::Compiler {
public:
    explicit ArxmlCompiler(const senda::domains::AutosarSchema& schema,
                           int max_skip_warnings = 10)
        : schema_(schema), max_skip_warnings_(max_skip_warnings) {}

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

        ParseState state{
            .schema = schema_,
            .builder = builder,
            .diags = diags,
            .file_path = path.string(),
            .stack = {},
            .context = &context,
            .max_skip_warnings = max_skip_warnings_,
        };

        XML_SetUserData(parser, &state);
        XML_SetElementHandler(parser, on_start_element, on_end_element);
        XML_SetCharacterDataHandler(parser, on_characters);

        // Parse
        auto status = XML_Parse(parser, content.data(),
                                static_cast<int>(content.size()), XML_TRUE);
        if (status == XML_STATUS_ERROR
            && XML_GetErrorCode(parser) != XML_ERROR_ABORTED) {
            diags.add({rupa::compiler::Severity::Error,
                       std::string("XML parse error: ")
                           + XML_ErrorString(XML_GetErrorCode(parser))
                           + " at line "
                           + std::to_string(XML_GetCurrentLineNumber(parser)),
                       {path.string(),
                         static_cast<uint32_t>(XML_GetCurrentLineNumber(parser)), 0}});
        }

        // Emit summary if skip warnings were capped
        if (state.skip_total_count > state.skip_warning_emitted) {
            int remaining = state.skip_total_count - state.skip_warning_emitted;
            diags.add({rupa::compiler::Severity::Warning,
                std::to_string(remaining) + " additional elements skipped",
                {path.string(), 0, 0}});
        }

        XML_ParserFree(parser);

        return rupa::compiler::CompileResult(
            std::move(fir), rupa::compiler::DomainExtensions{}, std::move(diags));
    }

private:
    static constexpr std::string_view exts_arr_[] = {".arxml"};
    std::span<const std::string_view> exts_{exts_arr_};
    const senda::domains::AutosarSchema& schema_;
    int max_skip_warnings_ = 10;

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
        rupa::compiler::CompileContext* context = nullptr;
        bool domain_resolved = false;
        bool domain_is_override = false;
        bool abort_parse = false;
        int skip_warning_emitted = 0;
        int skip_total_count = 0;
        int max_skip_warnings = 10;
    };

    // Map XSD filename to domain name
    static const char* map_schema_to_domain(std::string_view xsd_filename) {
        if (xsd_filename == "AUTOSAR_00052.xsd") return "autosar-r23-11";
        return nullptr;
    }

    // Extract XSD filename from xsi:schemaLocation value
    static std::string_view extract_xsd_filename(std::string_view schema_location) {
        auto space = schema_location.rfind(' ');
        if (space == std::string_view::npos) return schema_location;
        return schema_location.substr(space + 1);
    }

    static void XMLCALL on_start_element(void* user_data, const XML_Char* name,
                                          const XML_Char** attrs) {
        auto& state = *static_cast<ParseState*>(user_data);
        if (state.abort_parse) return;

        std::string_view tag(name);

        // Strip namespace prefix if present (e.g., "AR:AUTOSAR" -> "AUTOSAR")
        if (auto pos = tag.find(':'); pos != std::string_view::npos) {
            tag = tag.substr(pos + 1);
        }

        // On AUTOSAR root element, resolve domain from schema
        if (tag == "AUTOSAR" && !state.domain_resolved) {
            state.domain_resolved = true;

            // Extract xsi:schemaLocation from attributes
            std::string_view schema_location;
            for (int i = 0; attrs[i]; i += 2) {
                std::string_view attr_name(attrs[i]);
                if (attr_name == "xsi:schemaLocation" ||
                    attr_name.ends_with(":schemaLocation")) {
                    schema_location = std::string_view(attrs[i + 1]);
                    break;
                }
            }

            if (!schema_location.empty()) {
                auto xsd = extract_xsd_filename(schema_location);
                auto* domain_name = map_schema_to_domain(xsd);

                if (domain_name) {
                    // Known schema — request the named domain
                    auto* view = state.context->request_domain(domain_name);
                    if (!view) {
                        state.diags.add({rupa::compiler::Severity::Error,
                            std::string("domain '") + domain_name + "' is not available",
                            {state.file_path, 1, 0}});
                        state.abort_parse = true;
                        return;
                    }
                } else {
                    // Unknown schema — try default domain (override)
                    auto* view = state.context->request_default_domain();
                    if (!view) {
                        state.diags.add({rupa::compiler::Severity::Error,
                            "unsupported AUTOSAR schema '" + std::string(xsd)
                                + "'; use --domain to specify a domain",
                            {state.file_path, 1, 0}});
                        state.abort_parse = true;
                        return;
                    }
                    state.domain_is_override = true;
                }
            } else {
                // No schema annotation — try default domain
                auto* view = state.context->request_default_domain();
                if (view) {
                    state.domain_is_override = true;
                }
                // If no default available, continue without domain validation
                // (backwards-compatible with bare <AUTOSAR> elements)
            }
            // Continue — AUTOSAR is handled as a normal type lookup below
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

        // Emit skip warning when domain was overridden
        if (state.domain_is_override) {
            state.skip_total_count++;
            if (state.skip_warning_emitted < state.max_skip_warnings) {
                state.skip_warning_emitted++;
                state.diags.add({rupa::compiler::Severity::Warning,
                    "skipping unknown element '" + std::string(tag) + "'",
                    {state.file_path, 0, 0}});
            }
        }
    }

    static void XMLCALL on_end_element(void* user_data, const XML_Char* /*name*/) {
        auto& state = *static_cast<ParseState*>(user_data);
        if (state.abort_parse) return;

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
        if (state.abort_parse) return;

        if (state.stack.empty()) return;

        auto& frame = state.stack.back();
        if (frame.kind == FrameKind::Property) {
            frame.text.append(s, static_cast<size_t>(len));
        }
    }
};

}  // namespace senda
