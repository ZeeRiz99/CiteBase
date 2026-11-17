import { describe, expect, it } from "vitest";

import { canManage, grantableRoles, type Member } from "@/lib/team";

const member = (role: Member["role"], is_you = false): Member => ({
  user_id: "u",
  full_name: "N",
  email: "n@example.com",
  role,
  joined_at: "2026-11-17T00:00:00Z",
  is_you,
});

describe("team role rules", () => {
  it("grants only roles below the actor's own", () => {
    expect(grantableRoles("owner")).toEqual(["admin", "member", "viewer"]);
    expect(grantableRoles("admin")).toEqual(["member", "viewer"]);
    expect(grantableRoles("member")).toEqual(["viewer"]);
    expect(grantableRoles(undefined)).toEqual([]);
  });

  it("manages only people below the actor, never themselves", () => {
    expect(canManage("owner", member("admin"))).toBe(true);
    expect(canManage("admin", member("admin"))).toBe(false);
    expect(canManage("admin", member("owner"))).toBe(false);
    expect(canManage("admin", member("viewer"))).toBe(true);
    expect(canManage("owner", member("owner", true))).toBe(false);
  });
});
