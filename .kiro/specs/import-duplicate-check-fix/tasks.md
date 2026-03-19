# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Email-Based Duplicate Check
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For deterministic bugs, scope the property to the concrete failing case(s) to ensure reproducibility
  - Test that when CSV contains same name but different emails (e.g., "Ahmet Yılmaz" with ahmet@x.com and ahmet@y.com), both records should be imported (not skipped as duplicates)
  - The test assertions should match the Expected Behavior Properties from design: email varsa SADECE email kontrolü, farklı email = farklı kayıt
  - Run test on UNFIXED code (routes/import_wizard.py satır 763-779)
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: second record with different email is incorrectly skipped due to name match
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Name-Based Duplicate Check for No-Email Records
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (email olmayan kayıtlar)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - Same email records should still be marked as duplicates (3.1)
    - No-email records with same name should still be marked as duplicates (3.2)
    - duplicate_action behaviors (skip/update/create/create_with_suffix) should remain unchanged (3.3)
    - workspace_id isolation should be preserved (3.4)
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix for email-based duplicate check logic

  - [x] 3.1 Implement the fix in routes/import_wizard.py (satır 763-779)
    - Replace current if-if structure with if-elif structure
    - Email varsa SADECE email kontrolü yap: `if email: existing_contact = Contact.query.filter_by(..., email=email, ...).first()`
    - Email YOKSA SADECE isim kontrolü yap: `elif first_name: existing_contact = Contact.query.filter_by(..., first_name=first_name, last_name=last_name, ...).first()`
    - Remove the problematic `if not existing_contact and first_name` condition that causes fallback to name check
    - Add comments explaining the logic: "Email varsa sadece email, yoksa sadece isim ile kontrol"
    - _Bug_Condition: isBugCondition(input) where input.email IS NOT NULL AND input.email IS NOT EMPTY AND NOT existsInDB(input.email) AND existsInDB_byName(input.first_name, input.last_name)_
    - _Expected_Behavior: Email varsa SADECE email ile duplicate kontrolü, email yoksa SADECE isim ile duplicate kontrolü (design'daki expectedBehavior pseudocode)_
    - _Preservation: Same email duplicates (3.1), no-email name duplicates (3.2), duplicate_action behaviors (3.3), workspace isolation (3.4)_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Email-Based Duplicate Check
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify that same name + different email records are now imported correctly (not skipped)
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Name-Based Duplicate Check for No-Email Records
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all preservation behaviors still work: same email duplicates, no-email name duplicates, duplicate_action, workspace isolation

- [x] 4. Checkpoint - Ensure all tests pass
  - Run all tests (bug condition + preservation)
  - Verify imported_count is correct for test CSV files
  - Verify skipped_count is correct (no false positives)
  - Ask user if any questions arise or if additional validation is needed
