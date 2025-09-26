import { PublicClientApplication } from "@azure/msal-browser";

// Debug environment variables
console.log('AZURE_AD_CLIENT_ID:', process.env.NEXT_PUBLIC_AZURE_AD_CLIENT_ID);
console.log('AZURE_AD_TENANT_ID:', process.env.NEXT_PUBLIC_AZURE_AD_TENANT_ID);

// MSAL configuration
const msalConfig = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_AZURE_AD_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${process.env.NEXT_PUBLIC_AZURE_AD_TENANT_ID}`,
    redirectUri: typeof window !== 'undefined' ? window.location.origin + "/auth/callback" :
      process.env.NODE_ENV === 'production'
        ? "https://charlotte-frontend.azurewebsites.net/auth/callback"
        : "http://localhost:3000/auth/callback",
  },
  cache: {
    cacheLocation: "sessionStorage", // This configures where your cache will be stored
    storeAuthStateInCookie: false, // Set this to "true" if you are having issues on IE11 or Edge
  },
};

// Add scopes here for ID token to be used at Microsoft identity platform endpoints.
export const loginRequest = {
  scopes: ["User.Read"],
};

// Create the main myMSALObj instance
export const msalInstance = new PublicClientApplication(msalConfig);

export default msalConfig;