// File: assets/js/auth-check.js

console.log("auth-check.js loaded");

// Load Amplify core modules from the global AWS Amplify script (if available)
const Amplify = window.aws_amplify?.Amplify || window.Amplify;
const Auth = window.aws_amplify?.Auth || window.Amplify?.Auth;
const Hub = window.aws_amplify?.Hub || window.Amplify?.Hub;

// Save current page URL (origin + path) for potential redirects
const currentUrl = window.location.origin + window.location.pathname;

// Define Amplify Auth configuration using placeholders
const amplifyAuthConfig = {
  region: 'us-east-2', // Example: 'us-east-1'
  userPoolId: 'us-east-2_ObgxzZiq8', //write your Cognito User Pool ID here
  userPoolWebClientId: '3hkn733rjk2g1fkpmnmv3382ej', //write your Cognito User Pool Client ID here
  oauth: {
    domain: 'us-east-2obgxzziq8.auth.us-east-2.amazoncognito.com', //write your Cognito Domain here
    scope: ['email', 'openid', 'phone'], // OAuth scopes
    redirectSignIn: 'https://main.d3se10ik2qynbc.amplifyapp.com/admin-frontend/post-login.html', //write your Redirect Sign In URL here
    redirectSignOut: 'https://main.d3se10ik2qynbc.amplifyapp.com/index.html', //write your Redirect Sign Out URL here
    responseType: 'code', // OAuth flow to use (code for authorization code grant)
  }
};

// Safety checks make sure Amplify, Auth, and Hub are available
if (!Amplify || typeof Amplify.configure !== 'function') {
  console.error("Amplify not available or misconfigured.");
} else if (!Auth || !Hub) {
  console.error("Amplify.Auth or Amplify.Hub is missing. Cannot proceed.");
} else {
  // Initialize Amplify with the config above
  Amplify.configure({ Auth: amplifyAuthConfig });

  // Attempt to get the current user session immediately
  Auth.currentSession()
    .then(session => {
      console.log("Session exists:", session);
      checkUser(); // If session exists, check user details
    })
    .catch(err => {
      console.warn("No active session yet:", err.message);
    });

  /**
   * Main function: check if user is authenticated,
   * get their email, and update the UI.
   */
  async function checkUser(retry = false) {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");  // *** UPDATED ***

    // *** UPDATED START ***
    if (code) {
      console.log("Code found in URL. Attempting token exchange...");
      try {
        // Exchange the code for tokens
        await Auth.federatedSignIn(); 
        console.log("Token exchange successful. Reloading page...");
        // Reload without the code param, add ?from=cognito to know we came back
        window.location.replace(window.location.origin + window.location.pathname + "?from=cognito");
        return;
      } catch (err) {
        console.error("Token exchange failed:", err);
        return;
      }
    }
    // *** UPDATED END ***

    try {
      // Try to get the authenticated user
      const user = await Auth.currentAuthenticatedUser({ bypassCache: true });
      console.log("Raw user object:", user);

      // Get current session and decode ID token to extract email
      const session = await Auth.currentSession();
      const idTokenPayload = session.getIdToken().decodePayload();
      const email = idTokenPayload?.email || user.getUsername() || "Email not available";

      console.log("Email from ID token payload:", email);

      // Make email globally available to other scripts on the page
      window.petstayCurrentEmail = email;

      // Update the admin email display in the DOM
      updateAdminEmail(email);

      // If we came back from Cognito, clean up query params
      if (urlParams.get("from") === "cognito") {
        const cleanUrl = window.location.origin + window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);
      }
    } catch (err) {
      console.warn("Could not fetch authenticated user:", err.name, err.message);

      // If not retried yet, try again after 1 second (useful for slow auth)
      if (!retry) {
        console.warn("Retrying user check after 1s...");
        return setTimeout(() => checkUser(true), 1000);
      }

      // If still no session, update UI as not signed in
      updateAdminEmail("Not signed in");

      const justCameFromIndex = urlParams.get("from") === "index";
      const cameFromCognito = urlParams.get("from") === "cognito";

      // Avoid infinite redirect loops
      if (justCameFromIndex || cameFromCognito) {
        console.warn("Avoiding redirect loop after login");
        return;
      }

      // Build Cognito Hosted UI login URL and redirect to login
      const { domain, redirectSignIn } = amplifyAuthConfig.oauth;
      const clientId = amplifyAuthConfig.userPoolWebClientId;

      // Hosted UI authorization URL
      const loginUrl = new URL(`https://${domain}/oauth2/authorize`);
      loginUrl.searchParams.set('client_id', clientId);
      loginUrl.searchParams.set('response_type', 'code');
      loginUrl.searchParams.set('scope', 'email openid phone');
      loginUrl.searchParams.set('redirect_uri', redirectSignIn);

      console.log("Redirecting to login page...");
      window.location.replace(loginUrl.toString());
    }
  }

  /**
   * Update the admin email in the header or dropdown elements.
   * If not signed in, display fallback text.
   */
  function updateAdminEmail(email) {
    console.log("updateAdminEmail called with:", email);
    const fallback = email || "Not signed in";

    const emailEl = document.getElementById('adminEmail');
    if (emailEl) {
      emailEl.innerHTML = fallback;
      console.log("Email set in #adminEmail:", fallback);
    } else {
      console.warn("Element #adminEmail not found in DOM");
    }

    const dropdownEl = document.getElementById('adminEmailDropdown');
    if (dropdownEl) {
      dropdownEl.textContent = fallback;
      console.log("Email set in #adminEmailDropdown:", fallback);
    } else {
      console.warn("Element #adminEmailDropdown not found in DOM");
    }
  }

  /**
   * Listen for Amplify Auth events.
   * If user signs in, re-check user and show tokens in console for debugging.
   */
  Hub.listen('auth', async (data) => {
    const { payload } = data;
    if (payload.event === 'signIn') {
      console.log("Auth event: signIn");
      checkUser(true); // Re-check user details

      // Also log token payloads for debugging
      try {
        const session = await Auth.currentSession();
        console.log("ID Token Payload (Hub):", session.getIdToken().decodePayload());
        console.log("Access Token Payload (Hub):", session.getAccessToken().decodePayload());
      } catch (err) {
        console.warn("Failed to fetch token payload inside Hub listener:", err);
      }
    }
  });

  /**
   * Global sign-out function: signs out the user and redirects to Cognito logout.
   */
  window.signOutUser = function () {
    console.log("Sign out triggered");

    Auth.currentSession()
      .then(session => {
        console.log("Session found");
        const idToken = session.getIdToken().getJwtToken();
        return Auth.signOut({ global: true }).then(() => idToken);
      })
      .then(idToken => {
        const { domain, redirectSignOut } = amplifyAuthConfig.oauth;
        const clientId = amplifyAuthConfig.userPoolWebClientId;

        const logoutUrl = new URL(`https://${domain}/logout`);
        logoutUrl.searchParams.append('client_id', clientId);
        logoutUrl.searchParams.append('logout_uri', redirectSignOut);
        logoutUrl.searchParams.append('id_token_hint', idToken);

        console.log("Redirecting to:", logoutUrl.toString());
        window.location.replace(logoutUrl.toString());
      })
      .catch(err => {
        console.error("Sign out failed:", err);
        window.location.replace(amplifyAuthConfig.oauth.redirectSignOut);
      });
  };

  /**
   * When the page loads, attach the sign-out button event listener if found.
   */
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
      checkUser(); // Initial check

      const retryAttachSignOut = () => {
        const signOutEl = document.getElementById("signOutBtn");
        if (signOutEl) {
          console.log("Sign out button found, attaching handler");
          signOutEl.addEventListener("click", window.signOutUser);
        } else {
          console.warn("Sign out button NOT found, retrying...");
          setTimeout(retryAttachSignOut, 300);
        }
      };

      retryAttachSignOut();
    }, 500);
  });
}
