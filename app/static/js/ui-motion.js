document.documentElement.classList.add("js");

document.addEventListener("DOMContentLoaded", () => {
    const navbar = document.querySelector("[data-app-navbar]");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let navbarScrolled = null;
    let navbarFrame = null;

    const updateNavbar = () => {
        navbarFrame = null;
        const nextScrolled = window.scrollY > 12;
        if (navbar && nextScrolled !== navbarScrolled) {
            navbar.classList.toggle("is-scrolled", nextScrolled);
            navbarScrolled = nextScrolled;
        }
    };

    const scheduleNavbarUpdate = () => {
        if (navbarFrame === null) {
            navbarFrame = window.requestAnimationFrame(updateNavbar);
        }
    };

    updateNavbar();
    window.addEventListener("scroll", scheduleNavbarUpdate, { passive: true });

    const revealElements = document.querySelectorAll("[data-reveal]");
    if (reduceMotion || !("IntersectionObserver" in window)) {
        revealElements.forEach((element) => element.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    return;
                }
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            });
        },
        { rootMargin: "0px 0px -8%", threshold: 0.12 },
    );

    revealElements.forEach((element) => observer.observe(element));
});
