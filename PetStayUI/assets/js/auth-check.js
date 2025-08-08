

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
  userPoolId: 'us-east-2_yJEzY4ffU', //write your Cognito User Pool ID here
  userPoolWebClientId: '2qq961ihmelp8sqvf4j913tt35', //write your Cognito User Pool Client ID here
  oauth: {
    domain: 'us-east-2yjezy4ffu.auth.us-east-2.amazoncognito.com', //write your Cognito Domain here
    scope: ['email', 'openid', 'phone'], // OAuth scopes
    redirectSignIn: 'https://main.d3se10ik2qynbc.amplifyapp.com/admin-frontend/post-login.html', //write your Redirect Sign In URL here
    redirectSignOut: 'https://main.d3se10ik2qynbc.amplifyapp.com/index.html', //write your Redirect Sign Out URL here
    responseType: 'code', // OAuth flow to use (code for authorization code grant)
  }
};

  // Safety checks
  if (!Amplify || typeof Amplify.configure !== 'function') {
    console.error("Amplify not available or misconfigured.");
  } else if (!Auth || !Hub) {
    console.error("Amplify.Auth or Amplify.Hub is missing. Cannot proceed.");
  } else {
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

        // Clean up query params if came back from Cognito
        if (urlParams.get("from") === "cognito") {
          const cleanUrl = window.location.origin + window.location.pathname;
          window.history.replaceState({}, document.title, cleanUrl);
        }
      } catch (err) {
        console.warn("Could not fetch authenticated user:", err.name, err.message);

        if (!retry) {
          console.warn("Retrying user check after 1s...");
          return setTimeout(() => checkUser(true), 1000);
        }

        updateAdminEmail("Not signed in");

        const justCameFromIndex = urlParams.get("from") === "index";
        const cameFromCognito = urlParams.get("from") === "cognito";

        if (justCameFromIndex || cameFromCognito) {
          console.warn("Avoiding redirect loop after login");
          return;
        }

        // Redirect to Cognito Hosted UI login
        const { domain, redirectSignIn } = amplifyAuthConfig.oauth;
        const clientId = amplifyAuthConfig.userPoolWebClientId;

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

    // Expose checkUser globally so loader can call it
    window.checkUser = checkUser;

    /**
     * Listen for Amplify Auth events.
     * On sign in, re-check user and log tokens.
     */
    Hub.listen('auth', async (data) => {
      const { payload } = data;
      if (payload.event === 'signIn') {
        console.log("Auth event: signIn");
        checkUser(true);

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
     * Global sign-out function: signs out and redirects to Cognito logout.
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

    // Attach sign-out handler after DOM ready
    document.addEventListener('DOMContentLoaded', () => {
      setTimeout(() => {
        checkUser();

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

// The dynamic loader function — **outside** the guard
function loadDashboardAndAuth() {
  const dashboardScript = document.createElement('script');
  dashboardScript.src = '/assets/js/iot-dashboard.js';
  dashboardScript.onload = () => {
    if (!window.__PETSTAY_AUTH_CHECK_LOADED__) {
      const authScript = document.createElement('script');
      authScript.src = '/assets/js/auth-check.js';
      authScript.onload = () => {
        window.__PETSTAY_AUTH_CHECK_LOADED__ = true;

        const Auth = window.Amplify?.Auth;
        if (!Auth) return;

        Auth.currentAuthenticatedUser()
          .then(() => {
            console.log("User is authenticated — initializing IoT...");
            if (typeof connectToIoTDashboard === 'function') {
              connectToIoTDashboard();
            }

            if (typeof window.checkUser === 'function') {
              window.checkUser(true); // only update UI email, no redirect
            } else {
              console.warn("checkUser() not defined after auth-check.js load.");
            }
          })
          .catch(err => console.warn("User not signed in:", err.message));
      };
      authScript.onerror = () => console.error('Failed to load auth-check.js');
      document.body.appendChild(authScript);
    } else {
      console.log("auth-check.js already loaded — skipping");

      const Auth = window.Amplify?.Auth;
      if (Auth) {
        Auth.currentAuthenticatedUser()
          .then(() => {
            if (typeof window.checkUser === 'function') {
              window.checkUser(true);
            }
          })
          .catch(() => { });
      }
    }
  };
  dashboardScript.onerror = () => console.error('Failed to load iot-dashboard.js');
  document.body.appendChild(dashboardScript);
}
