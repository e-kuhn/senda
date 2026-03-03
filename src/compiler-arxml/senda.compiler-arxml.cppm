module;

#include <cstring>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <absl/container/flat_hash_map.h>
#include <utility>
#include <vector>
#include "xml_pull_parser.h"

export module senda.compiler.arxml;

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;
import rupa.diagnostics;
import senda.domains;
import senda.arxml_schema;

export namespace senda
{

class SchemaRegistry {
public:
    using BuilderFn = senda::domains::AutosarSchema(*)();

    void add(std::string_view xsd_filename, std::string_view domain_name,
             BuilderFn builder) {
        entries_.push_back({std::string(xsd_filename),
                           std::string(domain_name), builder, nullptr});
    }

    // Cheap lookup: XSD → domain name (no build)
    std::string_view find_domain_name(std::string_view xsd_filename) const {
        for (auto& e : entries_) {
            if (e.xsd_filename == xsd_filename) return e.domain_name;
        }
        return {};
    }

    // Check if a domain name is registered
    bool has_domain(std::string_view domain_name) const {
        for (auto& e : entries_) {
            if (e.domain_name == domain_name) return true;
        }
        return false;
    }

    // Lazy resolve: build schema on first access, cache it.
    // Returns non-const because the driver may move the domain out after caching.
    senda::domains::AutosarSchema* resolve(std::string_view xsd_filename) {
        for (auto& e : entries_) {
            if (e.xsd_filename == xsd_filename) {
                if (!e.cached) {
                    e.cached = std::make_unique<senda::domains::AutosarSchema>(
                        e.builder());
                }
                return e.cached.get();
            }
        }
        return nullptr;
    }

    // Lazy resolve by domain name
    senda::domains::AutosarSchema* resolve_by_domain(
        std::string_view domain_name) {
        for (auto& e : entries_) {
            if (e.domain_name == domain_name) {
                if (!e.cached) {
                    e.cached = std::make_unique<senda::domains::AutosarSchema>(
                        e.builder());
                }
                return e.cached.get();
            }
        }
        return nullptr;
    }

private:
    struct Entry {
        std::string xsd_filename;
        std::string domain_name;
        BuilderFn builder;
        std::unique_ptr<senda::domains::AutosarSchema> cached;
    };
    std::vector<Entry> entries_;
};

// Composite hash key for interned path: hash of StringId sequence.
// Incrementally computed as segments are pushed/popped.
struct PathKey {
    size_t hash = 0xcbf29ce484222325ULL;  // FNV-1a offset basis

    void push(fir::StringId id) {
        auto val = static_cast<uint64_t>(id);
        hash ^= val;
        hash *= 0x100000001b3ULL;  // FNV-1a prime
    }

    void pop(fir::StringId id) {
        auto val = static_cast<uint64_t>(id);
        // Reverse FNV-1a: multiply by modular inverse, then XOR
        hash *= 0xce965057aff6957bULL;  // modular inverse of FNV prime mod 2^64
        hash ^= val;
    }
};

class ArxmlCompiler : public rupa::compiler::Compiler {
public:
    ArxmlCompiler(SchemaRegistry& registry,
                  std::string_view default_domain = {},
                  int max_skip_warnings = 10)
        : registry_(registry),
          default_domain_(default_domain),
          max_skip_warnings_(max_skip_warnings) {}

    std::span<const std::string_view> extensions() const override {
        return exts_;
    }

    rupa::compiler::CompileResult compile(
        const std::filesystem::path& path,
        rupa::compiler::CompileContext& context) override
    {
        rupa::compiler::Diagnostics diags;

        // Memory-map the file
        if (!std::filesystem::exists(path)) {
            diags.add({rupa::compiler::Severity::Error,
                       "cannot open file: " + path.string(),
                       {path.string(), 0, 0}});
            return rupa::compiler::CompileResult(
                fir::Fir{}, rupa::compiler::DomainExtensions{}, std::move(diags));
        }
        rupa::diagnostics::SourceFile source(path);
        auto content = source.view();

        fir::Fir fir;
        rupa::fir_builder::FirBuilder builder(fir);

        ParseState state{
            .registry = registry_,
            .default_domain = default_domain_,
            .builder = builder,
            .diags = diags,
            .file_path = path.string(),
            .stack = {},
            .context = &context,
            .max_skip_warnings = max_skip_warnings_,
            .current_path_key = {},
            .current_path_ids = {},
            .path_index = {},
            .text_buf = {},
            .deferred_props = {},
        };

        XmlPullParser xml(content);

        while (true) {
            auto event = xml.next();
            if (event == XmlEvent::Eof) break;
            if (event == XmlEvent::Error) {
                diags.add({rupa::compiler::Severity::Error,
                           std::string("XML parse error: ") + xml.error_message()
                               + " at line " + std::to_string(xml.line()),
                           {path.string(), xml.line(), 0}});
                break;
            }
            if (state.abort_parse) break;

            switch (event) {
            case XmlEvent::StartElement:
                handle_start_element(state, xml);
                break;
            case XmlEvent::EndElement:
                handle_end_element(state);
                break;
            case XmlEvent::Characters:
                handle_characters(state, xml.text());
                break;
            default:
                break;
            }
        }

        resolve_references(state, fir);

        if (state.skip_total_count > state.skip_warning_emitted) {
            int remaining = state.skip_total_count - state.skip_warning_emitted;
            diags.add({rupa::compiler::Severity::Warning,
                std::to_string(remaining) + " additional elements skipped",
                {path.string(), 0, 0}});
        }

        return rupa::compiler::CompileResult(
            std::move(fir), rupa::compiler::DomainExtensions{}, std::move(diags));
    }

private:
    static constexpr std::string_view exts_arr_[] = {".arxml"};
    std::span<const std::string_view> exts_{exts_arr_};
    SchemaRegistry& registry_;
    std::string default_domain_;
    int max_skip_warnings_ = 10;

    // --- SAX state machine ---

    enum class FrameKind { Object, Property, Skip };

    struct Frame {
        FrameKind kind;
        // Object frame
        rupa::fir_builder::ObjectHandle obj{};
        const senda::domains::TypeInfo* type_info = nullptr;
        std::string_view xml_tag;  // element tag used to create this frame
        // Property frame
        rupa::domain::RoleHandle role{};
        rupa::fir_builder::ObjectHandle parent_obj{};
        const senda::domains::TypeInfo* target_type_info = nullptr;
        uint32_t text_start = 0;
        uint32_t text_len = 0;
        bool is_identity = false;  // true for SHORT-NAME capture
        bool is_reference = false;  // true for *-REF property frames
        // Single-element containment: this Object frame was created for an element
        // that is both a role on its parent AND a type (e.g., ADMIN-DATA).
        // On pop, use this role to defer containment to the enclosing Object frame.
        bool has_containment_role = false;
        fir::Id containment_role_id{0};
        // Path index tracking: true only when this object was created via SHORT-NAME
        // and pushed a path segment. Prevents anonymous objects from popping segments
        // they didn't push.
        bool pushed_path = false;
        // Skip frame
        int skip_depth = 0;
        // Deferred properties — indices into ParseState::deferred_props
        uint32_t deferred_start = 0;
        uint32_t deferred_count = 0;
    };

    struct ParseState {
        SchemaRegistry& registry;
        std::string_view default_domain;
        rupa::fir_builder::FirBuilder& builder;
        rupa::compiler::Diagnostics& diags;
        std::string file_path;
        std::vector<Frame> stack;
        rupa::compiler::CompileContext* context = nullptr;
        const senda::domains::AutosarSchema* schema = nullptr;
        bool domain_resolved = false;
        bool domain_is_override = false;
        bool abort_parse = false;
        int skip_warning_emitted = 0;
        int skip_total_count = 0;
        int max_skip_warnings = 10;
        // Path tracking for reference resolution
        PathKey current_path_key;
        std::vector<fir::StringId> current_path_ids;
        absl::flat_hash_map<size_t, fir::Id> path_index;
        // Root object tracking
        bool root_set = false;
        // Foreign module tracking
        fir::ModuleId current_module = fir::ModuleId{UINT16_MAX};
        bool module_registered = false;
        // Shared text buffer: Property frames record offsets into this
        std::string text_buf;
        // Shared deferred-property buffer: Object frames record (role_id, value_id)
        // pairs here, flushed atomically via flush_properties when the Object
        // frame pops. This ensures contiguous property spans even when nested
        // objects interleave property creation.
        std::vector<std::pair<fir::Id, fir::Id>> deferred_props;
    };

    // Extract XSD filename from xsi:schemaLocation value
    static std::string_view extract_xsd_filename(std::string_view schema_location) {
        auto space = schema_location.rfind(' ');
        if (space == std::string_view::npos) return schema_location;
        return schema_location.substr(space + 1);
    }

    // Register the domain's module in the compile FIR when domain is resolved.
    static void register_domain_module(ParseState& state,
                                       std::string_view domain_name) {
        if (state.module_registered) return;
        auto& target = state.builder.target();
        auto mod_name_id = target.intern(domain_name);
        state.current_module = target.addModule(mod_name_id);
        target.addDomain(mod_name_id);
        state.module_registered = true;
    }

    static void handle_start_element(ParseState& state, XmlPullParser& xml) {
        auto tag = xml.tag();

        // On AUTOSAR root element, resolve domain from schema
        if (tag == "AUTOSAR" && !state.domain_resolved) {
            state.domain_resolved = true;

            // Lazy attribute scan for xsi:schemaLocation
            std::string_view schema_location;
            while (xml.next_attr()) {
                auto attr_name = xml.attr_name();
                if (attr_name == "schemaLocation") {
                    schema_location = xml.attr_value();
                    break;
                }
            }

            if (!schema_location.empty()) {
                auto xsd = extract_xsd_filename(schema_location);
                auto domain_name = state.registry.find_domain_name(xsd);

                if (!domain_name.empty()) {
                    // Known XSD — resolve schema lazily and request domain
                    state.schema = state.registry.resolve(xsd);
                    auto* view = state.context->request_domain(domain_name);
                    if (!view) {
                        state.diags.add({rupa::compiler::Severity::Error,
                            "domain '" + std::string(domain_name)
                                + "' is not available",
                            {state.file_path, 1, 0}});
                        state.abort_parse = true;
                        return;
                    }
                    register_domain_module(state, domain_name);
                } else {
                    // Unknown XSD — try default domain (CLI override)
                    auto* view = state.context->request_default_domain();
                    if (!view) {
                        state.diags.add({rupa::compiler::Severity::Error,
                            "unsupported AUTOSAR schema '" + std::string(xsd)
                                + "'; use --domain to specify a domain",
                            {state.file_path, 1, 0}});
                        state.abort_parse = true;
                        return;
                    }
                    // Resolve schema for the override domain
                    if (!state.default_domain.empty()) {
                        state.schema = state.registry.resolve_by_domain(
                            state.default_domain);
                        register_domain_module(state, state.default_domain);
                    }
                    state.domain_is_override = true;
                }
            } else {
                // No schema annotation — try default domain
                auto* view = state.context->request_default_domain();
                if (view) {
                    if (!state.default_domain.empty()) {
                        state.schema = state.registry.resolve_by_domain(
                            state.default_domain);
                        register_domain_module(state, state.default_domain);
                    }
                    state.domain_is_override = true;
                }
            }
            // Continue — AUTOSAR is handled as a normal type lookup below
        }

        // If top of stack is Skip, increment depth
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Skip) {
            state.stack.back().skip_depth++;
            return;
        }

        // ---- Object frame: check roles FIRST, then fall through to type ----
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Object) {
            auto& parent = state.stack.back();

            // SHORT-NAME provides identity for the parent object
            if (tag == "SHORT-NAME" && !parent.obj.valid()) {
                Frame frame{};
                frame.kind = FrameKind::Property;
                frame.is_identity = true;
                state.stack.push_back(std::move(frame));
                return;
            }

            if (parent.type_info) {
                auto* role_info = parent.type_info->roles.find(tag);
                if (role_info) {
                    // Ensure parent object exists — generalized eager creation
                    // (subsumes the old AUTOSAR-only special case).
                    if (!parent.obj.valid()) {
                        auto type_id = parent.type_info->handle.id;
                        if (state.module_registered) {
                            type_id = state.builder.target().addForeignRef(
                                state.current_module,
                                static_cast<uint32_t>(type_id));
                        }
                        parent.obj = state.builder.begin_object(
                            parent.xml_tag,
                            rupa::fir_builder::TypeHandle{type_id});
                        if (!state.root_set) {
                            state.builder.set_root_object(parent.obj);
                            state.root_set = true;
                        }
                    }

                    // Check for single-element containment:
                    // tag is BOTH a role on the parent AND a registered type.
                    // Create an Object frame with embedded containment info.
                    // Skip for reference roles — those need text capture.
                    const senda::domains::TypeInfo* nested_type = nullptr;
                    if (!role_info->is_reference && state.schema) {
                        nested_type = state.schema->tag_to_type.find(tag);
                    }

                    if (nested_type) {
                        // Single-element containment: Object frame with role info
                        auto role_id = role_info->role.id;
                        if (state.module_registered) {
                            role_id = state.builder.target().addForeignRef(
                                state.current_module,
                                static_cast<uint32_t>(role_id));
                        }
                        Frame frame{};
                        frame.kind = FrameKind::Object;
                        frame.type_info = nested_type;
                        frame.xml_tag = tag;
                        frame.obj = {};  // created eagerly on first child role
                        frame.deferred_start = static_cast<uint32_t>(
                            state.deferred_props.size());
                        frame.has_containment_role = true;
                        frame.containment_role_id = role_id;
                        state.stack.push_back(std::move(frame));
                        return;
                    }

                    // Standard property (scalar, reference, or wrapper element)
                    Frame frame{};
                    frame.kind = FrameKind::Property;
                    frame.role = role_info->role;
                    frame.parent_obj = parent.obj;
                    frame.is_reference = role_info->is_reference;
                    if (state.schema) {
                        auto* ti = state.schema->handle_to_type.find(
                            role_info->target_type_id);
                        if (ti) frame.target_type_info = *ti;
                    }
                    state.stack.push_back(std::move(frame));
                    return;
                }
            }
            // Fall through to type lookup (handles types that aren't roles
            // of the current parent, e.g., unexpected nested types)
        }

        // ---- Property frame: resolve children against target type ----
        if (!state.stack.empty() && state.stack.back().kind == FrameKind::Property) {
            auto& prop = state.stack.back();

            // Try as a role on the property's target type
            if (prop.target_type_info) {
                auto* role_info = prop.target_type_info->roles.find(tag);
                if (role_info) {
                    Frame frame{};
                    frame.kind = FrameKind::Property;
                    frame.role = role_info->role;
                    frame.parent_obj = prop.parent_obj;
                    frame.is_reference = role_info->is_reference;
                    if (state.schema) {
                        auto* ti = state.schema->handle_to_type.find(
                            role_info->target_type_id);
                        if (ti) frame.target_type_info = *ti;
                    }
                    state.stack.push_back(std::move(frame));
                    return;
                }
            }

            // Try as a top-level type (contained object)
            const senda::domains::TypeInfo* nested_type_info = nullptr;
            if (state.schema) {
                nested_type_info = state.schema->tag_to_type.find(tag);
            }
            if (nested_type_info) {
                Frame frame{};
                frame.kind = FrameKind::Object;
                frame.type_info = nested_type_info;
                frame.xml_tag = tag;
                frame.obj = {};
                frame.deferred_start = static_cast<uint32_t>(
                    state.deferred_props.size());
                state.stack.push_back(std::move(frame));
                return;
            }

            // Fall back to the property's target type when the element name
            // differs from the registered type tag (e.g. VFC-IREF)
            if (prop.target_type_info) {
                Frame frame{};
                frame.kind = FrameKind::Object;
                frame.type_info = prop.target_type_info;
                frame.xml_tag = tag;
                frame.obj = {};
                frame.deferred_start = static_cast<uint32_t>(
                    state.deferred_props.size());
                state.stack.push_back(std::move(frame));
                return;
            }
        }

        // ---- Type lookup: root elements and unmatched types ----
        const senda::domains::TypeInfo* type_info = nullptr;
        if (state.schema) {
            type_info = state.schema->tag_to_type.find(tag);
        }
        if (type_info) {
            Frame frame{};
            frame.kind = FrameKind::Object;
            frame.type_info = type_info;
            frame.xml_tag = tag;
            frame.obj = {};
            frame.deferred_start = static_cast<uint32_t>(
                state.deferred_props.size());
            state.stack.push_back(std::move(frame));
            return;
        }

        // ---- Unknown element: skip ----
        Frame frame{};
        frame.kind = FrameKind::Skip;
        frame.skip_depth = 1;
        state.stack.push_back(std::move(frame));

        state.skip_total_count++;
        if (state.skip_warning_emitted < state.max_skip_warnings) {
            state.skip_warning_emitted++;
            state.diags.add({rupa::compiler::Severity::Warning,
                "skipping unknown element '" + std::string(tag) + "'",
                {state.file_path, 0, 0}});
        }
    }

    // Defer a (role_id, value_id) pair to the nearest enclosing Object frame.
    static void defer_property(ParseState& state, fir::Id role_id,
                               fir::Id value_id) {
        for (auto it = state.stack.rbegin(); it != state.stack.rend(); ++it) {
            if (it->kind == FrameKind::Object) {
                it->deferred_count++;
                state.deferred_props.emplace_back(role_id, value_id);
                return;
            }
        }
    }

    static void handle_end_element(ParseState& state) {
        if (state.stack.empty()) return;

        auto& frame = state.stack.back();

        switch (frame.kind) {
        case FrameKind::Skip:
            if (--frame.skip_depth > 0) return;
            break;

        case FrameKind::Property: {
            std::string_view frame_text;
            if (frame.text_len > 0) {
                frame_text = std::string_view(
                    state.text_buf.data() + frame.text_start, frame.text_len);
            }
            if (frame.is_identity && !frame_text.empty()) {
                // SHORT-NAME captured — create the parent object
                if (state.stack.size() >= 2) {
                    auto& parent = state.stack[state.stack.size() - 2];
                    if (parent.kind == FrameKind::Object && parent.type_info
                        && !parent.obj.valid()) {
                        auto type_id = parent.type_info->handle.id;
                        if (state.module_registered) {
                            type_id = state.builder.target().addForeignRef(
                                state.current_module,
                                static_cast<uint32_t>(type_id));
                        }
                        parent.obj = state.builder.begin_object(
                            frame_text,
                            rupa::fir_builder::TypeHandle{type_id});
                        // Set root object (first top-level object)
                        if (!state.root_set) {
                            state.builder.set_root_object(parent.obj);
                            state.root_set = true;
                        }
                        // Register in path index for reference resolution
                        auto identity_sid = state.builder.target().as<fir::ObjectDef>(
                            parent.obj.id).identity;
                        state.current_path_ids.push_back(identity_sid);
                        state.current_path_key.push(identity_sid);
                        state.path_index[state.current_path_key.hash] = parent.obj.id;
                        parent.pushed_path = true;
                    }
                }
            } else if (!frame_text.empty() && frame.parent_obj.valid()) {
                auto role_id = frame.role.id;
                if (state.module_registered) {
                    role_id = state.builder.target().addForeignRef(
                        state.current_module,
                        static_cast<uint32_t>(role_id));
                }
                if (frame.is_reference) {
                    // Skip whitespace-only text (inter-element indentation
                    // from *-REF elements containing child elements).
                    bool all_ws = true;
                    for (auto c : frame_text) {
                        if (c != ' ' && c != '\t' && c != '\n' && c != '\r') {
                            all_ws = false;
                            break;
                        }
                    }
                    if (!all_ws) {
                        auto val_id = state.builder.create_reference_value(
                            frame_text);
                        defer_property(state, role_id, val_id);
                    }
                } else {
                    auto val_sid = state.builder.target().intern(frame_text);
                    auto val_id = state.builder.target().add<fir::ValueDef>(
                        fir::ValueKind::String, val_sid);
                    defer_property(state, role_id, val_id);
                }
            }
            // Reclaim buffer space
            state.text_buf.resize(frame.text_start);
            break;
        }

        case FrameKind::Object:
            // Eagerly create anonymous object if needed: type without SHORT-NAME
            // that either has deferred properties or a containment role.
            if (!frame.obj.valid() && frame.type_info
                && (frame.deferred_count > 0 || frame.has_containment_role)) {
                auto type_id = frame.type_info->handle.id;
                if (state.module_registered) {
                    type_id = state.builder.target().addForeignRef(
                        state.current_module,
                        static_cast<uint32_t>(type_id));
                }
                frame.obj = state.builder.begin_object(
                    frame.xml_tag,
                    rupa::fir_builder::TypeHandle{type_id});
            }

            if (frame.obj.valid()) {
                // Flush ALL deferred properties atomically
                auto span = std::span<const std::pair<fir::Id, fir::Id>>(
                    state.deferred_props.data() + frame.deferred_start,
                    frame.deferred_count);
                state.builder.flush_properties(frame.obj, span);
                state.deferred_props.resize(frame.deferred_start);

                // Containment: prefer embedded role (single-element containment)
                if (frame.has_containment_role) {
                    // Skip past self (frame is still on the stack as back())
                    for (auto it = state.stack.rbegin() + 1;
                         it != state.stack.rend(); ++it) {
                        if (it->kind == FrameKind::Object) {
                            it->deferred_count++;
                            state.deferred_props.emplace_back(
                                frame.containment_role_id, frame.obj.id);
                            break;
                        }
                    }
                }
                // Existing: containment via enclosing Property frame
                else if (state.stack.size() >= 2) {
                    auto& below = state.stack[state.stack.size() - 2];
                    if (below.kind == FrameKind::Property
                        && below.parent_obj.valid()) {
                        auto role_id = below.role.id;
                        if (state.module_registered) {
                            role_id = state.builder.target().addForeignRef(
                                state.current_module,
                                static_cast<uint32_t>(role_id));
                        }
                        for (auto it = state.stack.rbegin() + 2;
                             it != state.stack.rend(); ++it) {
                            if (it->kind == FrameKind::Object) {
                                it->deferred_count++;
                                state.deferred_props.emplace_back(
                                    role_id, frame.obj.id);
                                break;
                            }
                        }
                    }
                }

                // Path index: only pop if this object pushed a segment
                if (frame.pushed_path && !state.current_path_ids.empty()) {
                    state.current_path_key.pop(state.current_path_ids.back());
                    state.current_path_ids.pop_back();
                }
            }
            break;
        }

        state.stack.pop_back();
    }

    static void resolve_references(ParseState& state, fir::Fir& fir) {
        if (state.path_index.empty()) return;

        int resolved = 0;
        int unresolved = 0;

        fir.forEachNode([&](fir::Id /*id*/, fir::Node& node) {
            if (node.kind != fir::NodeKind::ValueDef) return;
            auto& val = static_cast<fir::ValueDef&>(node);
            if (val.value_kind != fir::ValueKind::Reference) return;
            if (val.ref_target != fir::Id{UINT32_MAX}) return;

            // Compute path hash from interned segments — no string allocation
            auto segs = fir.pathSegments(val.segment_start, val.segment_count);
            PathKey key;
            for (auto& seg : segs) {
                auto& seg_val = fir.as<fir::ValueDef>(seg.value);
                key.push(seg_val.string_val);
            }

            auto it = state.path_index.find(key.hash);
            if (it != state.path_index.end()) {
                val.ref_target = it->second;
                resolved++;
            } else {
                unresolved++;
            }
        });

        if (resolved > 0 || unresolved > 0) {
            state.diags.add({rupa::compiler::Severity::Note,
                std::to_string(resolved) + " references resolved, "
                    + std::to_string(unresolved) + " unresolved",
                {state.file_path, 0, 0}});
        }
    }

    static void handle_characters(ParseState& state, std::string_view text) {
        if (state.stack.empty()) return;

        auto& frame = state.stack.back();
        if (frame.kind == FrameKind::Property) {
            if (frame.text_len == 0) {
                frame.text_start = static_cast<uint32_t>(state.text_buf.size());
            }
            state.text_buf.append(text.data(), text.size());
            frame.text_len += static_cast<uint32_t>(text.size());
        }
    }
};

}  // namespace senda
