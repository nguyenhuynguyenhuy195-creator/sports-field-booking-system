document.documentElement.classList.add("js");

document.addEventListener("DOMContentLoaded", () => {
    const navbar = document.querySelector("[data-app-navbar]");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const updateNavbar = () => {
        if (navbar) {
            navbar.classList.toggle("is-scrolled", window.scrollY > 12);
        }
    };

    updateNavbar();
    window.addEventListener("scroll", updateNavbar, { passive: true });

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
