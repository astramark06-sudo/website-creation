"""Exhaustive policy matrix and rejection tests for the future auth adapter."""
import unittest
from dataclasses import replace

from scripts.creator_access import Action, Principal, Role, allowed, require_access


class AccessTests(unittest.TestCase):
    def test_complete_matrix(self):
        matrix = {
            Role.VIEWER: {"read_records", "read_relations"},
            Role.EDITOR: {"read_records", "read_relations", "create_record", "edit_record"},
            Role.OWNER: {"read_records", "read_relations", "create_record", "edit_record",
                         "delete_record", "export_data", "manage_members", "manage_schema"},
        }
        self.assertEqual(set(matrix), set(Role))
        self.assertEqual(matrix[Role.OWNER], {action.value for action in Action})
        for role, grants in matrix.items():
            principal = Principal("user-1", "workspace-1", role, True)
            for action in Action:
                with self.subTest(role=role, action=action):
                    permitted = action.value in grants
                    self.assertIs(allowed(principal, "workspace-1", action), permitted)
                    if permitted:
                        self.assertIsNone(require_access(principal, "workspace-1", action))
                    else:
                        with self.assertRaises(PermissionError):
                            require_access(principal, "workspace-1", action)

    def test_cross_workspace_and_inactive_denied_for_every_action(self):
        for role in Role:
            principal = Principal("user-1", "workspace-1", role, True)
            for action in Action:
                with self.subTest(role=role, action=action):
                    self.assertFalse(allowed(principal, "workspace-2", action))
                    self.assertFalse(allowed(replace(principal, active=False), "workspace-1", action))
                    self.assertFalse(allowed(None, "workspace-1", action))

    def test_malformed_values_fail_closed(self):
        owner = Principal("user-1", "workspace-1", Role.OWNER, True)
        for principal in ({"subject": "user-1", "role": "owner"},
                          replace(owner, role="owner"), replace(owner, role=[]),
                          replace(owner, active=1), replace(owner, subject=""),
                          replace(owner, workspace="../other"), replace(owner, subject=None)):
            for action in Action:
                self.assertFalse(allowed(principal, "workspace-1", action))
        for action in ("read_records", None, [], "unknown"):
            self.assertFalse(allowed(owner, "workspace-1", action))
        for workspace in ("", None, [], "../workspace-1", "workspace-1 "):
            self.assertFalse(allowed(owner, workspace, Action.READ_RECORDS))

    def test_revoked_membership_and_role_change(self):
        owner = Principal("user-1", "workspace-1", Role.OWNER, True)
        self.assertTrue(allowed(owner, "workspace-1", Action.MANAGE_MEMBERS))
        self.assertFalse(allowed(replace(owner, active=False), "workspace-1", Action.MANAGE_MEMBERS))
        self.assertFalse(allowed(replace(owner, role=Role.VIEWER), "workspace-1", Action.EDIT_RECORD))


if __name__ == "__main__":
    unittest.main()
