// Credential Management API — not in TypeScript's default lib (Chrome-only)
interface PasswordCredentialData {
  id: string;
  password: string;
  name?: string;
}

interface PasswordCredential extends Credential {
  readonly id: string;
  readonly type: string;
  readonly password: string;
}

declare var PasswordCredential: {
  prototype: PasswordCredential;
  new(data: PasswordCredentialData): PasswordCredential;
};

interface Window {
  PasswordCredential?: typeof PasswordCredential;
}
