//index.js

// Redirect to Customer Booking page
// 🔗 Redirect to Customer Booking page
document.getElementById('left-button')?.addEventListener('click', () => {
  window.location.href = '/customer/new-booking.html';
});


// Redirect to Admin Login via Cognito Hosted UI
document.getElementById('right-button')?.addEventListener('click', () => {
  sessionStorage.setItem("adminLogin", "1"); // Set session storage flag

  const clientId = window.PETSTAY_CONFIG.COGNITO_USER_POOL_CLIENT_ID;
  const domain = window.PETSTAY_CONFIG.COGNITO_DOMAIN;
  const redirectUri = encodeURIComponent(window.PETSTAY_CONFIG.REDIRECT_ADMIN_SIGN_IN_URL);

  const loginUrl = `https://${domain}/login?client_id=${clientId}&response_type=code&scope=email+openid+phone&redirect_uri=${redirectUri}`;

  window.location.href = loginUrl;
});

// Hover effect logic for split landing page
const content = document.querySelector(".content");
const left = document.querySelector(".left");
const right = document.querySelector(".right");

left?.addEventListener("mouseenter", () => content?.classList.add("hover-left"));
left?.addEventListener("mouseleave", () => content?.classList.remove("hover-left"));

right?.addEventListener("mouseenter", () => content?.classList.add("hover-right"));
right?.addEventListener("mouseleave", () => content?.classList.remove("hover-right"));