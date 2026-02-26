module;

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <span>
#include <sstream>
#include <string>
#include <string_view>
#include <utility>
#include <pugixml.hpp>

export module senda.compiler.arxml;

import rupa.compiler;
import rupa.domain;
import rupa.fir;
import rupa.fir.builder;

export namespace senda
{

class ArxmlCompiler : public rupa::compiler::Compiler {
public:
    std::span<const std::string_view> extensions() const override {
        return exts_;
    }

    rupa::compiler::CompileResult compile(
        const std::filesystem::path& path,
        rupa::compiler::CompileContext& context) override
    {
        rupa::compiler::Diagnostics diags;

        // Parse XML
        pugi::xml_document doc;
        auto parse_result = doc.load_file(path.c_str());
        if (!parse_result) {
            diags.add({rupa::compiler::Severity::Error,
                       std::string("XML parse error: ") + parse_result.description(),
                       {path.string(), 0, 0}});
            return rupa::compiler::CompileResult(
                fir::Fir{}, rupa::compiler::DomainExtensions{}, std::move(diags));
        }

        // Find root AUTOSAR element (with or without namespace)
        auto root = doc.child("AUTOSAR");
        if (!root) {
            // Try with namespace prefix
            root = doc.child("AR:AUTOSAR");
        }
        if (!root) {
            diags.add({rupa::compiler::Severity::Error,
                       "missing <AUTOSAR> root element",
                       {path.string(), 0, 0}});
            return rupa::compiler::CompileResult(
                fir::Fir{}, rupa::compiler::DomainExtensions{}, std::move(diags));
        }

        // Request the AUTOSAR domain
        const rupa::domain::DomainView* domain = context.request_domain("autosar-r23-11");
        if (!domain) {
            diags.add({rupa::compiler::Severity::Error,
                       "AUTOSAR domain 'autosar-r23-11' not available",
                       {path.string(), 0, 0}});
            return rupa::compiler::CompileResult(
                fir::Fir{}, rupa::compiler::DomainExtensions{}, std::move(diags));
        }

        // Build FIR from ARXML content
        fir::Fir fir;
        rupa::fir_builder::FirBuilder builder(fir);

        // Walk AR-PACKAGES recursively
        walk_packages(root, builder, context, *domain, diags, path.string());

        return rupa::compiler::CompileResult(
            std::move(fir), rupa::compiler::DomainExtensions{}, std::move(diags));
    }

private:
    static constexpr std::string_view exts_arr_[] = {".arxml"};
    std::span<const std::string_view> exts_{exts_arr_};

    /// Convert AUTOSAR XML tag name (UPPER-KEBAB-CASE) to PascalCase type name.
    /// e.g. "I-SIGNAL" -> "ISignal", "ECU-INSTANCE" -> "EcuInstance"
    static std::string tag_to_type_name(std::string_view tag) {
        std::string result;
        result.reserve(tag.size());
        bool capitalize_next = true;
        for (char c : tag) {
            if (c == '-') {
                capitalize_next = true;
            } else if (capitalize_next) {
                result += static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
                capitalize_next = false;
            } else {
                result += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
            }
        }
        return result;
    }

    /// Convert AUTOSAR XML child tag name to camelCase role name.
    /// e.g. "SHORT-NAME" -> "shortName", "I-SIGNAL-TYPE" -> "iSignalType"
    static std::string tag_to_role_name(std::string_view tag) {
        std::string result;
        result.reserve(tag.size());
        bool capitalize_next = false;
        bool first_word = true;
        for (char c : tag) {
            if (c == '-') {
                capitalize_next = true;
            } else if (capitalize_next) {
                if (first_word) {
                    result += static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
                } else {
                    result += static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
                }
                capitalize_next = false;
                first_word = false;
            } else {
                result += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
                first_word = false;
            }
        }
        return result;
    }

    void walk_packages(
        pugi::xml_node parent,
        rupa::fir_builder::FirBuilder& builder,
        rupa::compiler::CompileContext& context,
        const rupa::domain::DomainView& domain,
        rupa::compiler::Diagnostics& diags,
        const std::string& file_path)
    {
        for (auto pkg : parent.children("AR-PACKAGES")) {
            for (auto ar_pkg : pkg.children("AR-PACKAGE")) {
                walk_package(ar_pkg, builder, context, domain, diags, file_path);
            }
        }
        // Also handle direct AR-PACKAGE children (flat structure)
        for (auto ar_pkg : parent.children("AR-PACKAGE")) {
            walk_package(ar_pkg, builder, context, domain, diags, file_path);
        }
    }

    void walk_package(
        pugi::xml_node pkg,
        rupa::fir_builder::FirBuilder& builder,
        rupa::compiler::CompileContext& context,
        const rupa::domain::DomainView& domain,
        rupa::compiler::Diagnostics& diags,
        const std::string& file_path)
    {
        // Process ELEMENTS in this package
        auto elements = pkg.child("ELEMENTS");
        if (elements) {
            for (auto elem : elements.children()) {
                process_element(elem, builder, domain, diags, file_path);
            }
        }

        // Recurse into sub-packages
        walk_packages(pkg, builder, context, domain, diags, file_path);
    }

    void process_element(
        pugi::xml_node elem,
        rupa::fir_builder::FirBuilder& builder,
        const rupa::domain::DomainView& domain,
        rupa::compiler::Diagnostics& diags,
        const std::string& file_path)
    {
        auto tag = std::string_view(elem.name());
        auto type_name = tag_to_type_name(tag);

        // Look up type in domain
        auto type_handle = domain.find_type(type_name);
        if (!type_handle.valid()) {
            diags.add({rupa::compiler::Severity::Warning,
                       "unknown AUTOSAR type: " + type_name + " (from <" + std::string(tag) + ">)",
                       {file_path, 0, 0}});
            return;
        }

        // Get SHORT-NAME for identity
        auto short_name_node = elem.child("SHORT-NAME");
        std::string identity = short_name_node
            ? short_name_node.text().as_string()
            : "";

        if (identity.empty()) {
            diags.add({rupa::compiler::Severity::Warning,
                       "element <" + std::string(tag) + "> has no SHORT-NAME",
                       {file_path, 0, 0}});
            return;
        }

        // Create object instance
        auto obj = builder.begin_object(identity, rupa::fir_builder::TypeHandle{type_handle.id});

        // Map child elements to properties
        for (auto child : elem.children()) {
            auto child_tag = std::string_view(child.name());
            if (child_tag == "SHORT-NAME") continue;  // already handled as identity

            auto role_name = tag_to_role_name(child_tag);
            auto role_handle = domain.find_role(type_handle, role_name);

            if (!role_handle.valid()) {
                // Skip unknown roles silently — ARXML has many elements
                // we don't model yet
                continue;
            }

            // Extract text content as string value
            auto text = child.text().as_string();
            if (text[0] != '\0') {
                builder.add_property(obj, rupa::fir_builder::RoleHandle{role_handle.id},
                                     std::string_view(text));
            }
        }
    }
};

}  // namespace senda
