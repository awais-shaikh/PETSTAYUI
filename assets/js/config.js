window.PETSTAY_CONFIG = {
  AWS_REGION: "us-east-2",
  COGNITO_USER_POOL_ID: "us-east-2_ObgxzZiq8",
  COGNITO_USER_POOL_CLIENT_ID: "3hkn733rjk2g1fkpmnmv3382ej",
  COGNITO_DOMAIN: "us-east-2obgxzziq8.auth.us-east-2.amazoncognito.com",
  REDIRECT_SIGN_IN_URL: "https://main.d2qk7y64cxtqr2.amplifyapp.com/admin-frontend/post-login.html",
  REDIRECT_SIGN_OUT_URL: "https://main.d2qk7y64cxtqr2.amplifyapp.com/index.html",
  BOOKINGS_API_URL: "{{BOOKINGS_API_URL}}",
  ROOMS_AVAILABILITY_API_URL: "{{ROOMS_AVAILABILITY_API_URL}}",
  NEW_BOOKING_API_URL: "{{NEW_BOOKING_API_URL}}",
  CHECKIN_API_URL: "{{CHECKIN_API_URL}}"
};

// Safety check: crash the page if placeholders were not replaced
for (const key in window.PETSTAY_CONFIG) {
  if (window.PETSTAY_CONFIG[key].includes("{{") || window.PETSTAY_CONFIG[key].includes("}}")) {
    throw new Error(`Missing config value: ${key}. Did you forget to set environment variables?`);
  }
}
