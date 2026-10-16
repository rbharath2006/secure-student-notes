document.addEventListener("DOMContentLoaded", () => {
    const menu = document.getElementById("mobileMenu");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("mobileOverlay");

    const closeMenu = () => {
        sidebar?.classList.remove("open");
        overlay?.classList.remove("show");
    };

    menu?.addEventListener("click", () => {
        sidebar?.classList.toggle("open");
        overlay?.classList.toggle("show");
    });

    overlay?.addEventListener("click", closeMenu);

    document.querySelectorAll("[data-confirm]").forEach(element => {
        const eventType = element.matches("form") ? "submit" : "click";

        element.addEventListener(eventType, event => {
            if (!window.confirm(element.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll(".password-toggle").forEach(button => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.target);
            if (!input) return;
            const visible = input.type === "text";
            input.type = visible ? "password" : "text";
            button.textContent = visible ? "Show" : "Hide";
        });
    });

    const password = document.getElementById("password");
    const meter = document.getElementById("passwordMeter");
    const hint = document.getElementById("passwordHint");

    password?.addEventListener("input", () => {
        const value = password.value;
        let score = 0;
        if (value.length >= 8) score++;
        if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score++;
        if (/\d/.test(value)) score++;
        if (/[^A-Za-z0-9]/.test(value)) score++;

        const widths = ["0%", "25%", "50%", "75%", "100%"];
        const messages = ["Use a strong password.", "Weak password.", "Fair password.", "Good password.", "Strong password."];
        meter.style.width = widths[score];
        meter.style.background = score < 2 ? "#ef4444" : score < 3 ? "#f59e0b" : "#22c55e";
        hint.textContent = messages[score];
    });
});
