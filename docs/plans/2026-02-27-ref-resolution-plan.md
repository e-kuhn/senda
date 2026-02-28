# Cross-Reference Resolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Capture all AUTOSAR `*-REF` elements as `ValueKind::Reference` path values in the FIR, then resolve them to `ObjectDef` handles post-parse, eliminating ~5.6K skips.

**Architecture:** Schema-driven approach — extend the schema converter to emit `is_reference` flags and inner REF element roles, add a `add_reference()` method to FirBuilder, and add a resolution pass to the ARXML compiler. Six batches, each independently completable.

**Tech Stack:** Python (schema converter), C++23 (FirBuilder, ARXML compiler), CMake, pytest

**Design doc:** `docs/plans/2026-02-27-ref-resolution-design.md`

---

## Batch 1: Schema Model + Parser (Python)

### Task 1: Add `inner_ref_tag` to schema model

**Files:**
- Modify: `tools/schema-converter/schema_model.py:84-95` (`InternalMember`), `tools/schema-converter/schema_model.py:19-30` (`ExportMember`)

**Step 1: Write the failing test**

Add to `tools/schema-converter/tests/test_schema_parser.py`:

```python
class TestRefMemberInnerTag(unittest.TestCase):
    """Test that Pattern B wrapper REFs extract inner_ref_tag."""

    def test_direct_ref_has_no_inner_ref_tag(self):
        """Direct *-REF elements (Pattern A) should have inner_ref_tag = None."""
        xsd = '''<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                             xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:group name="I-SIGNAL">
            <xsd:sequence>
              <xsd:element maxOccurs="1" minOccurs="0" name="SYSTEM-SIGNAL-REF">
                <xsd:annotation><xsd:appinfo source="tags">
                  mmt.qualifiedName="ISignal.systemSignal";pureMM.minOccurs="0";pureMM.maxOccurs="1"
                </xsd:appinfo></xsd:annotation>
                <xsd:complexType><xsd:simpleContent>
                  <xsd:extension base="AR:REF">
                    <xsd:attribute name="DEST" type="xsd:string" use="required"/>
                  </xsd:extension>
                </xsd:simpleContent></xsd:complexType>
              </xsd:element>
            </xsd:sequence>
          </xsd:group>
        </xsd:schema>'''
        schema = parse_schema_from_string(xsd)
        exported = export_schema(schema)
        isignal = next(c for c in exported.composites if c.name == "ISignal")
        ref_member = next(m for m in isignal.members if m.is_reference)
        self.assertIsNone(ref_member.inner_ref_tag)

    def test_wrapped_ref_has_inner_ref_tag(self):
        """Pattern B wrapper REFs should extract inner_ref_tag from inner element."""
        xsd = '''<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                             xmlns:AR="http://autosar.org/schema/r4.0">
          <xsd:group name="I-SIGNAL-TRIGGERING">
            <xsd:sequence>
              <xsd:element maxOccurs="1" minOccurs="0" name="I-SIGNAL-PORT-REFS">
                <xsd:annotation><xsd:appinfo source="tags">
                  mmt.qualifiedName="ISignalTriggering.iSignalPort";pureMM.minOccurs="0";pureMM.maxOccurs="-1"
                </xsd:appinfo></xsd:annotation>
                <xsd:complexType>
                  <xsd:choice maxOccurs="unbounded" minOccurs="0">
                    <xsd:element name="I-SIGNAL-PORT-REF">
                      <xsd:complexType><xsd:simpleContent>
                        <xsd:extension base="AR:REF">
                          <xsd:attribute name="DEST" type="xsd:string" use="required"/>
                        </xsd:extension>
                      </xsd:simpleContent></xsd:complexType>
                    </xsd:element>
                  </xsd:choice>
                </xsd:complexType>
              </xsd:element>
            </xsd:sequence>
          </xsd:group>
        </xsd:schema>'''
        schema = parse_schema_from_string(xsd)
        exported = export_schema(schema)
        triggering = next(c for c in exported.composites if c.name == "ISignalTriggering")
        ref_member = next(m for m in triggering.members if m.is_reference)
        self.assertEqual(ref_member.inner_ref_tag, "I-SIGNAL-PORT-REF")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tools/schema-converter/tests/test_schema_parser.py::TestRefMemberInnerTag -v`
Expected: FAIL — `ExportMember` has no `inner_ref_tag` attribute.

**Step 3: Add `inner_ref_tag` field to both dataclasses**

In `tools/schema-converter/schema_model.py`, add to `ExportMember` (after line 30):
```python
inner_ref_tag: str | None = None   # Pattern B: inner REF element XML tag name
```

Add to `InternalMember` (after line 95 or wherever the last field is):
```python
inner_ref_tag: str | None = None
```

Ensure `_to_export_member()` (or equivalent conversion) propagates `inner_ref_tag` from `InternalMember` to `ExportMember`. Search for where `ExportMember` is constructed from `InternalMember` and add the field mapping.

**Step 4: Extract `inner_ref_tag` in `_get_ref_member()`**

In `tools/schema-converter/schema_parser.py`, inside `_get_ref_member()` at lines 527-532 (Path B), after the extension element is found via the `xsd:choice → xsd:element` path, extract the inner element's name:

```python
# After line 535 (the for loop that tries paths)
# If Path B matched, extract inner element name
if ext is not None:
    inner_elem = _get_path(elem, ["xsd:complexType", "xsd:choice", "xsd:element"])
    if inner_elem is not None and "name" in inner_elem.attrib:
        member.inner_ref_tag = inner_elem.attrib["name"]
```

The key: Path B walks through `xsd:choice → xsd:element` — that `xsd:element` IS the inner REF element, and its `name` attribute is what we want.

**Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tools/schema-converter/tests/test_schema_parser.py::TestRefMemberInnerTag -v`
Expected: PASS

**Step 6: Run all existing parser tests for regression**

Run: `python3 -m pytest tools/schema-converter/tests/test_schema_parser.py -v`
Expected: All pass.

**Step 7: Commit**

```bash
git add tools/schema-converter/schema_model.py tools/schema-converter/schema_parser.py tools/schema-converter/tests/test_schema_parser.py
git commit -m "feat(schema): extract inner_ref_tag for Pattern B wrapper REFs"
```

---

## Batch 2: C++ Generator (Python)

### Task 2: Emit `is_reference` in `RoleInfo` constructor

**Files:**
- Modify: `tools/schema-converter/cpp_generator.py:239-240` (role emission line)
- Test: `tools/schema-converter/tests/test_cpp_generator.py`

**Step 1: Write the failing test**

Add to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
class TestRoleInfoIsReference(unittest.TestCase):
    """Test that is_reference flag is emitted in RoleInfo."""

    def test_non_reference_role_emits_false(self):
        schema = ExportSchema(
            composites=[ExportComposite(
                name="MyType", xml_name="MY-TYPE",
                members=[ExportMember(
                    name="child", types=["ChildType"],
                    xml_element_name="CHILD", is_reference=False,
                )],
            )],
            primitives=[ExportPrimitive(name="ChildType", xml_name="CHILD-TYPE")],
            enums=[], domain="test",
        )
        code = generate_domain_builder(schema)
        self.assertIn("false}", code)  # is_reference = false in RoleInfo

    def test_reference_role_emits_true(self):
        schema = ExportSchema(
            composites=[ExportComposite(
                name="MyType", xml_name="MY-TYPE",
                members=[ExportMember(
                    name="targetRef", types=["TargetType"],
                    xml_element_name="TARGET-REF", is_reference=True,
                )],
            )],
            primitives=[ExportPrimitive(name="TargetType", xml_name="TARGET-TYPE")],
            enums=[], domain="test",
        )
        code = generate_domain_builder(schema)
        self.assertIn("true}", code)  # is_reference = true in RoleInfo
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tools/schema-converter/tests/test_cpp_generator.py::TestRoleInfoIsReference -v`
Expected: FAIL — current RoleInfo emission doesn't include `is_reference`.

**Step 3: Update RoleInfo emission**

In `tools/schema-converter/cpp_generator.py`, modify the `info.roles.add(...)` line at ~line 239-240:

Before:
```python
w('        info.roles.add("%s", RoleInfo{rupa::domain::RoleHandle{%s.id}, static_cast<uint32_t>(%s.id)});'
  % (xml_elem, rvar, target_type_var))
```

After — need to pass `is_reference` from the member. This requires threading the `is_reference` flag through `role_handles` and `_all_roles()`.

Update `role_handles` accumulation (~line 134) to include `is_reference`:
```python
role_handles[c.name].append((rvar, xml_elem, role_name, target_type, m.is_reference))
```

Update `_all_roles()` return type to include `is_reference`.

Update the emission line:
```python
for rvar, xml_elem, _role_name, target_type_var, is_ref in roles:
    ref_str = "true" if is_ref else "false"
    w('        info.roles.add("%s", RoleInfo{rupa::domain::RoleHandle{%s.id}, static_cast<uint32_t>(%s.id), %s});'
      % (xml_elem, rvar, target_type_var, ref_str))
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tools/schema-converter/tests/test_cpp_generator.py::TestRoleInfoIsReference -v`
Expected: PASS

**Step 5: Run all generator tests for regression**

Run: `python3 -m pytest tools/schema-converter/tests/test_cpp_generator.py -v`
Expected: All pass (existing tests may need `is_reference` tuples updated if `_all_roles` signature changed).

**Step 6: Commit**

```bash
git add tools/schema-converter/cpp_generator.py tools/schema-converter/tests/test_cpp_generator.py
git commit -m "feat(generator): emit is_reference flag in RoleInfo"
```

---

### Task 3: Inject inner REF roles into target type lookup tables

This is the critical change that eliminates Pattern B skips. When a wrapper member (e.g., `I-SIGNAL-PORT-REFS` on type `ISignalTriggering`) has `inner_ref_tag = "I-SIGNAL-PORT-REF"`, the C++ generator must add `"I-SIGNAL-PORT-REF"` as a role on the target type (`ISignalPort`) in the lookup table.

**Files:**
- Modify: `tools/schema-converter/cpp_generator.py` — `_all_roles()` or equivalent, lookup table emission
- Test: `tools/schema-converter/tests/test_cpp_generator.py`

**Step 1: Write the failing test**

Add to `tools/schema-converter/tests/test_cpp_generator.py`:

```python
class TestInnerRefRoleInjection(unittest.TestCase):
    """Test that Pattern B wrappers inject inner REF roles into target types."""

    def test_inner_ref_tag_injected_into_target_type(self):
        schema = ExportSchema(
            composites=[
                ExportComposite(
                    name="ISignalTriggering", xml_name="I-SIGNAL-TRIGGERING",
                    members=[ExportMember(
                        name="iSignalPort", types=["ISignalPort"],
                        xml_element_name="I-SIGNAL-PORT-REFS",
                        is_reference=True,
                        inner_ref_tag="I-SIGNAL-PORT-REF",
                    )],
                ),
                ExportComposite(
                    name="ISignalPort", xml_name="I-SIGNAL-PORT",
                    members=[],
                ),
            ],
            primitives=[], enums=[], domain="test",
        )
        code = generate_domain_module(schema)
        # The wrapper role should appear on ISignalTriggering
        self.assertIn('"I-SIGNAL-PORT-REFS"', code)
        # The inner REF role should be injected into ISignalPort's TypeInfo
        # Look for ISignalPort's tag_to_type block containing I-SIGNAL-PORT-REF
        isignal_port_block = code[code.index('"I-SIGNAL-PORT"'):]
        self.assertIn('"I-SIGNAL-PORT-REF"', isignal_port_block)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tools/schema-converter/tests/test_cpp_generator.py::TestInnerRefRoleInjection -v`
Expected: FAIL — `I-SIGNAL-PORT-REF` not present in generated code for `ISignalPort`.

**Step 3: Implement inner REF role injection**

In `tools/schema-converter/cpp_generator.py`:

1. Build an injection map after the `role_handles` loop (~line 139):

```python
# Build inner REF role injection: target_type_name -> [(inner_ref_tag, rvar, target_type_var)]
inner_ref_roles: dict[str, list[tuple[str, str, str]]] = {}
for c in composites:
    for i, m in enumerate(c.members):
        if m.inner_ref_tag and m.types:
            target_name = m.types[0]
            if target_name not in inner_ref_roles:
                inner_ref_roles[target_name] = []
            cvar = type_vars[c.name]
            rvar = _role_var(cvar, i)
            target_var = type_vars.get(target_name, "string_t")
            inner_ref_roles[target_name].append((m.inner_ref_tag, rvar, target_var))
```

2. In `_all_roles()` (or at lookup table emission ~line 233), append injected roles:

```python
def _all_roles(type_name):
    roles = [...]  # existing logic
    # Append injected inner REF roles
    for inner_tag, rvar, target_var in inner_ref_roles.get(type_name, []):
        roles.append((rvar, inner_tag, None, target_var, True))  # is_reference=True
    return roles
```

3. Update the role count in FrozenMap constructor to account for injected roles.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tools/schema-converter/tests/test_cpp_generator.py::TestInnerRefRoleInjection -v`
Expected: PASS

**Step 5: Run all tests for regression**

Run: `python3 -m pytest tools/schema-converter/tests/ -v`
Expected: All pass.

**Step 6: Commit**

```bash
git add tools/schema-converter/cpp_generator.py tools/schema-converter/tests/test_cpp_generator.py
git commit -m "feat(generator): inject inner REF roles into target type lookup tables"
```

---

## Batch 3: Domain Header + Regeneration (C++)

### Task 4: Add `is_reference` to `RoleInfo` struct

**Files:**
- Modify: `src/domains/senda.domains.cppm:14-17`

**Step 1: Update the struct**

In `src/domains/senda.domains.cppm`, modify `RoleInfo`:

Before:
```cpp
struct RoleInfo {
    rupa::domain::RoleHandle role;
    uint32_t target_type_id;
};
```

After:
```cpp
struct RoleInfo {
    rupa::domain::RoleHandle role;
    uint32_t target_type_id;
    bool is_reference = false;
};
```

The default `false` ensures existing aggregate-initialized `RoleInfo{handle, id}` in domain files still compile.

**Step 2: Build to verify compilation**

Run: `cmake --build --preset debug`
Expected: Builds successfully. All existing domain files use `RoleInfo{handle, id}` which gets `is_reference = false` by default.

**Step 3: Run tests**

Run: `cd build-debug && ctest --output-on-failure`
Expected: All 3 tests pass.

**Step 4: Commit**

```bash
git add src/domains/senda.domains.cppm
git commit -m "feat(domains): add is_reference flag to RoleInfo"
```

---

### Task 5: Regenerate all 5 domain files

**Files:**
- Modify: `src/domains/senda.domains.r*.cppm` (5 files)

**Step 1: Regenerate domains**

Run the schema converter for each schema version. Check `tools/schema-converter/` for the generation script or command. Likely:

```bash
source .venv/bin/activate
python tools/schema-converter/main.py schema/AUTOSAR_00048.xsd --output src/domains/
python tools/schema-converter/main.py schema/AUTOSAR_00049.xsd --output src/domains/
python tools/schema-converter/main.py schema/AUTOSAR_00050.xsd --output src/domains/
python tools/schema-converter/main.py schema/AUTOSAR_00051.xsd --output src/domains/
python tools/schema-converter/main.py schema/AUTOSAR_00052.xsd --output src/domains/
```

Verify the command by checking `tools/schema-converter/main.py` for the actual CLI interface. Adjust arguments as needed.

**Step 2: Verify generated files contain `is_reference`**

```bash
grep -c "true}" src/domains/senda.domains.r20-11.cppm   # should show reference roles with true
grep -c "false}" src/domains/senda.domains.r20-11.cppm  # should show non-reference roles with false
```

**Step 3: Verify inner REF roles injected**

```bash
grep "I-SIGNAL-PORT-REF" src/domains/senda.domains.r20-11.cppm  # should appear in ISignalPort TypeInfo
```

**Step 4: Build**

Run: `cmake --build --preset debug`
Expected: Builds successfully.

**Step 5: Run tests**

Run: `cd build-debug && ctest --output-on-failure`
Expected: All 3 tests pass (behavior unchanged — compiler doesn't use `is_reference` yet).

**Step 6: Commit**

```bash
git add src/domains/senda.domains.r*.cppm
git commit -m "feat(domains): regenerate with is_reference flags and inner REF roles"
```

---

## Batch 4: FirBuilder Reference API (C++ in Rupa submodule)

### Task 6: Add `add_reference()` to FirBuilder

**Files:**
- Modify: `external/rupa/src/fir/rupa.fir-builder.cppm:95-132`

**Step 1: Check path segment storage API**

Read `external/rupa/src/fir/rupa.fir.cppm` to find:
- How `path_segments_` is stored (likely `std::vector<PathSegment>`)
- Whether there's an existing `add_path_segment()` or similar method
- How to get the current segment count for `segment_start`

Also check existing usage of `ValueKind::Reference` in `external/rupa/src/sema/rupa.sema-lower-instances.cppm` — this is where the Rupa sema pass creates reference values from parsed Rupa source. Copy the pattern.

**Step 2: Implement `add_reference()`**

In `external/rupa/src/fir/rupa.fir-builder.cppm`, after the existing `add_property` overloads (~line 118):

```cpp
void add_reference(ObjectHandle obj, RoleHandle role, std::string_view path) {
    // Parse AUTOSAR path: "/pkg/sub/name" → segments ["pkg", "sub", "name"]
    uint32_t seg_start = static_cast<uint32_t>(target_.path_segments().size());
    uint16_t seg_count = 0;

    size_t pos = 0;
    if (!path.empty() && path[0] == '/') pos = 1;  // skip leading /

    while (pos < path.size()) {
        auto next = path.find('/', pos);
        auto segment = path.substr(pos, next - pos);
        if (!segment.empty()) {
            auto str_id = target_.intern(segment);
            auto seg_val_id = target_.add<fir::ValueDef>(str_id);
            target_.add_path_segment(fir::PathSegment{
                fir::PathSegmentKind::Id, seg_val_id});
            seg_count++;
        }
        pos = (next == std::string_view::npos) ? path.size() : next + 1;
    }

    // Create reference ValueDef
    auto val_id = target_.add<fir::ValueDef>(fir::ValueKind::Reference);
    auto& val = target_.get<fir::ValueDef>(val_id);
    val.segment_start = seg_start;
    val.segment_count = seg_count;
    // ref_target stays UINT32_MAX (unresolved)

    append_property(obj, role, val_id);
}
```

**Important:** Adapt this code to match the actual `Fir` API. The method names (`path_segments()`, `add_path_segment()`, `get<>()`) may differ. Check `rupa.fir.cppm` and the existing sema lowering code for the real API.

**Step 3: Build**

Run: `cmake --build --preset debug`
Expected: Builds successfully.

**Step 4: Run tests**

Run: `cd build-debug && ctest --output-on-failure`
Expected: All 3 tests pass.

**Step 5: Commit (inside rupa submodule)**

```bash
cd external/rupa
git add src/fir/rupa.fir-builder.cppm
git commit -m "feat(fir): add add_reference() to FirBuilder for cross-reference paths"
cd ../..
git add external/rupa
git commit -m "chore: update rupa submodule (add_reference API)"
```

---

## Batch 5: ARXML Compiler Changes (C++)

### Task 7: Add `is_reference` to Frame and dispatch in `on_end_element`

**Files:**
- Modify: `src/compiler-arxml/senda.compiler-arxml.cppm:192-205` (Frame struct), `src/compiler-arxml/senda.compiler-arxml.cppm:328-409` (on_start_element), `src/compiler-arxml/senda.compiler-arxml.cppm:412-451` (on_end_element)

**Step 1: Add `is_reference` to Frame struct**

In `src/compiler-arxml/senda.compiler-arxml.cppm`, add to `Frame` (~line 202):
```cpp
bool is_reference = false;  // true for *-REF property frames
```

**Step 2: Set `is_reference` when creating Property frames**

In `on_start_element`, wherever a Property frame is created from a role lookup result:

```cpp
// When role is found in type_info->roles or target_type_info->roles:
frame.is_reference = role_it->second.is_reference;
```

There are multiple places where Property frames are created (direct child of Object frame, child of Property frame via composition flattening). Update ALL of them.

**Step 3: Dispatch in `on_end_element`**

In `on_end_element` (~lines 437-442), update the Property frame text handling:

Before:
```cpp
} else if (!frame.text.empty() && frame.parent_obj.valid()) {
    state.builder.add_property(
        frame.parent_obj, rupa::fir_builder::RoleHandle{frame.role.id},
        std::string_view(frame.text));
}
```

After:
```cpp
} else if (!frame.text.empty() && frame.parent_obj.valid()) {
    if (frame.is_reference) {
        state.builder.add_reference(
            frame.parent_obj, rupa::fir_builder::RoleHandle{frame.role.id},
            std::string_view(frame.text));
    } else {
        state.builder.add_property(
            frame.parent_obj, rupa::fir_builder::RoleHandle{frame.role.id},
            std::string_view(frame.text));
    }
}
```

**Step 4: Build**

Run: `cmake --build --preset debug`
Expected: Builds successfully.

**Step 5: Run tests**

Run: `cd build-debug && ctest --output-on-failure`
Expected: All 3 tests pass.

**Step 6: Commit**

```bash
git add src/compiler-arxml/senda.compiler-arxml.cppm
git commit -m "feat(arxml): dispatch to add_reference() for is_reference roles"
```

---

### Task 8: Add path index and reference resolution pass

**Files:**
- Modify: `src/compiler-arxml/senda.compiler-arxml.cppm:207-222` (ParseState), `src/compiler-arxml/senda.compiler-arxml.cppm` (on_start_element, on_end_element, compile function)

**Step 1: Add path index to ParseState**

In `ParseState` (~line 222):
```cpp
std::vector<std::string> current_path;  // stack of SHORT-NAME segments for path tracking
std::unordered_map<std::string, rupa::fir::Id> path_index;  // full path -> ObjectDef Id
```

**Step 2: Update `on_end_element` to build path index**

When a SHORT-NAME Property frame closes and creates an object (the identity case at ~lines 426-435), after `begin_object()` is called, register the object in the path index:

```cpp
// After begin_object() creates the parent object:
state.current_path.push_back(std::string(frame.text));
std::string full_path = "/" + join(state.current_path, "/");
state.path_index[full_path] = parent.obj.id;
```

Implement a simple `join()` helper or build the path inline.

**Step 3: Pop path segments when leaving Object frames**

In `on_end_element`, when an Object frame is popped:
```cpp
case FrameKind::Object:
    if (frame.obj.valid()) {
        state.current_path.pop_back();
    }
    break;
```

**Step 4: Add resolution pass**

Add a function after the SAX parse completes:

```cpp
void resolve_references(ParseState& state) {
    auto& fir = state.builder.target();  // or however you access the Fir
    int resolved = 0;
    int unresolved = 0;

    // Walk all nodes, find ValueDef with ValueKind::Reference
    for (auto& node : fir.nodes()) {
        if (node->kind() != fir::NodeKind::ValueDef) continue;
        auto& val = static_cast<fir::ValueDef&>(*node);
        if (val.value_kind != fir::ValueKind::Reference) continue;
        if (val.ref_target != fir::Id{UINT32_MAX}) continue;  // already resolved

        // Reconstruct path from segments
        std::string path = "/";
        for (uint16_t i = 0; i < val.segment_count; i++) {
            auto& seg = fir.path_segments()[val.segment_start + i];
            auto& seg_val = fir.get<fir::ValueDef>(seg.value);
            auto seg_str = fir.lookup(seg_val.string_val);
            if (i > 0) path += "/";
            path += seg_str;
        }

        // Resolve
        auto it = state.path_index.find(path);
        if (it != state.path_index.end()) {
            val.ref_target = it->second;
            resolved++;
        } else {
            unresolved++;
        }
    }

    if (unresolved > 0) {
        state.diags.add({rupa::compiler::Severity::Warning,
            std::to_string(unresolved) + " unresolved cross-references",
            state.file_path, 0});
    }
}
```

**Important:** Adapt this code to the actual Fir API. Method names for node iteration, path segment access, and string lookup will vary. Check existing Fir usage in `rupa.sema-lower-instances.cppm` or `rupa.fir.cppm`.

**Step 5: Call resolution pass after parsing**

In the `compile()` function (or wherever `XML_Parse` is called), after the parse loop completes:

```cpp
// After XML_Parse loop:
resolve_references(state);
```

**Step 6: Build**

Run: `cmake --build --preset debug`
Expected: Builds successfully.

**Step 7: Run tests**

Run: `cd build-debug && ctest --output-on-failure`
Expected: All 3 tests pass.

**Step 8: Commit**

```bash
git add src/compiler-arxml/senda.compiler-arxml.cppm
git commit -m "feat(arxml): add path index and reference resolution pass"
```

---

## Batch 6: Integration + Verification

### Task 9: Verify skip count reduction

**Files:**
- None (verification only)

**Step 1: Run against R20-11 ARXML**

```bash
./build-debug/senda import test/data/arxml/vehicle-comms-r20-11.arxml
```

Expected: Skip count drops from ~5,622 significantly (ideally to near zero for `*-REF` elements). Some non-REF skips may remain.

**Step 2: Run against R4.3.1 ARXML**

```bash
./build-debug/senda import --domain r19-11 test/data/arxml/vehicle-platform-r4-3-1.arxml
```

Expected: Skip count drops proportionally from ~73,374.

**Step 3: Analyze remaining skips**

If any `*-REF` elements are still skipped, investigate:
- Are they IREF child REFs not covered?
- Are they REF-CONDITIONAL inner REFs not covered?
- Are they a pattern not covered by the four categories?

**Step 4: Run all tests**

```bash
cd build-debug && ctest --output-on-failure
python3 -m pytest tools/schema-converter/tests/ -v
```

Expected: All pass.

**Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(arxml): address remaining skip edge cases"
```

---

### Task 10: Update memory and clean up

**Step 1: Update MEMORY.md**

Update `/Users/ekuhn/.claude/projects/-Users-ekuhn-CLionProjects-senda/memory/MEMORY.md` with:
- Cross-reference resolution completed
- New skip counts after the fix
- Any remaining known gaps

**Step 2: PR, merge, cleanup**

Use `superpowers:finishing-a-development-branch` skill.
