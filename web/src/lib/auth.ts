import { WebStorageStateStore } from "oidc-client-ts";
import type { AuthProviderProps, AuthContextProps } from "react-oidc-context";

const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID ?? "";
const loginDomain = import.meta.env.VITE_COGNITO_DOMAIN ?? "";

export const oidcConfig: AuthProviderProps = {
  authority: import.meta.env.VITE_COGNITO_AUTHORITY ?? "",
  client_id: clientId,
  // Debe coincidir exactamente con el callback registrado en Cognito, sin barra final.
  redirect_uri: window.location.origin,
  response_type: "code",
  scope: "openid email profile",
  automaticSilentRenew: true,
  // La PWA debe seguir con sesión al cerrarla: sessionStorage la perdería.
  userStore: new WebStorageStateStore({ store: window.localStorage }),
  onSigninCallback: () => {
    // Saca el `code` de un solo uso de la barra de direcciones y del historial.
    window.history.replaceState({}, document.title, window.location.pathname);
  },
};

export function logoutUrl(): string {
  const params = new URLSearchParams({
    client_id: clientId,
    logout_uri: window.location.origin,
  });
  return `${loginDomain}/logout?${params}`;
}

export async function signOut(auth: AuthContextProps): Promise<void> {
  try {
    await auth.revokeTokens(["refresh_token"]);
  } catch {
    // Sin red no se puede revocar; igual se cierra la sesión en este dispositivo.
  }
  await auth.removeUser();
  // Cierra también la sesión de Cognito: si no, el próximo login entraría sin pedir nada.
  window.location.assign(logoutUrl());
}
