/*
    This code enables menue bar on mobile devices using browser
*/
document.addEventListener("DOMContentLoaded", () => {
    const menuBtn = document.querySelector(".mobile-menu-button");
    const closeMenuBtn = document.querySelector(".close-mobile-menu");
    const menu = document.querySelector('.only-mobile-menu');
    const side = document.querySelector('.side-overlay')
    menuBtn.onclick = (event) => {
        menu.classList.add("active");
        side.classList.add("show");
        document.body.classList.add("scroll-hide-sm")
    }

    closeMenuBtn.onclick = (event) => {
        menu.classList.remove("active");
        side.classList.remove("show");
        document.body.classList.remove("scroll-hide-sm")
    }
    
    // WPA for manifest.json app
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker
            .register("/static/sw.js")
            .then((registration) => {
                console.log("Service Worker Registered!", registration);
            })
            .catch((error) => {
                console.log("Service Worker Registration Failed:", error);
            });
    }


})