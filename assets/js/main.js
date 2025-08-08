// main.js

const sidebarNavWrapper = document.querySelector(".sidebar-nav-wrapper");
const mainWrapper = document.querySelector(".main-wrapper");
const overlay = document.querySelector(".overlay");
const menuToggleButton = document.querySelector("#menu-toggle");
const menuToggleButtonIcon = document.querySelector("#menu-toggle i");
const sidebarClose = document.querySelector(".sidebar-close");

// ✅ Toggle sidebar
if (menuToggleButton && sidebarNavWrapper && overlay && mainWrapper && menuToggleButtonIcon) {
  menuToggleButton.addEventListener("click", () => {
    sidebarNavWrapper.classList.toggle("active");
    overlay.classList.add("active");
    mainWrapper.classList.toggle("active");

    if (document.body.clientWidth > 1200) {
      if (menuToggleButtonIcon.classList.contains("lni-chevron-left")) {
        menuToggleButtonIcon.classList.remove("lni-chevron-left");
        menuToggleButtonIcon.classList.add("lni-menu");
      } else {
        menuToggleButtonIcon.classList.remove("lni-menu");
        menuToggleButtonIcon.classList.add("lni-chevron-left");
      }
    } else {
      if (menuToggleButtonIcon.classList.contains("lni-chevron-left")) {
        menuToggleButtonIcon.classList.remove("lni-chevron-left");
        menuToggleButtonIcon.classList.add("lni-menu");
      }
    }
  });
}

// ✅ Close sidebar on overlay click
if (overlay && sidebarNavWrapper && mainWrapper) {
  overlay.addEventListener("click", () => {
    sidebarNavWrapper.classList.remove("active");
    overlay.classList.remove("active");
    mainWrapper.classList.remove("active");
    if (menuToggleButtonIcon && menuToggleButtonIcon.classList.contains("lni-chevron-left")) {
      menuToggleButtonIcon.classList.remove("lni-chevron-left");
      menuToggleButtonIcon.classList.add("lni-menu");
    }
  });
}

// ✅ Close sidebar on sidebar close button click
if (sidebarClose && sidebarNavWrapper && overlay && mainWrapper) {
  sidebarClose.addEventListener("click", () => {
    sidebarNavWrapper.classList.remove("active");
    overlay.classList.remove("active");
    mainWrapper.classList.remove("active");
    if (menuToggleButtonIcon && menuToggleButtonIcon.classList.contains("lni-chevron-left")) {
      menuToggleButtonIcon.classList.remove("lni-chevron-left");
      menuToggleButtonIcon.classList.add("lni-menu");
    }
  });
}

