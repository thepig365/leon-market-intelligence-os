type Claims = {
  sub?: unknown;
  email?: unknown;
  app_metadata?: unknown;
};

export type LMIOIdentity = {
  id: string;
  email: string;
  role: "owner" | "operator" | "reviewer";
};

function metadata(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function identityFromClaims(claims: Claims | null | undefined): LMIOIdentity | null {
  if (!claims || typeof claims.sub !== "string" || !claims.sub) return null;
  const app = metadata(claims.app_metadata);
  if (app.status !== "active" || app.private_beta_access !== true) return null;
  if (!["owner", "operator", "reviewer"].includes(String(app.role))) return null;
  return {
    id: claims.sub,
    email: typeof claims.email === "string" ? claims.email : "",
    role: app.role as LMIOIdentity["role"],
  };
}
