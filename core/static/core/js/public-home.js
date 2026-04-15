/* Public home page JS — extracted from public_home.html */

function submitContact(e) {
    e.preventDefault();
    const btn = document.getElementById('contactBtn');
    const errorDiv = document.getElementById('contactError');
    errorDiv.style.display = 'none';
    btn.disabled = true;
    btn.textContent = 'Sending...';

    fetch('/api/contact/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: document.getElementById('contactName').value,
            company: document.getElementById('contactCompany').value,
            email: document.getElementById('contactEmail').value,
            message: document.getElementById('contactMessage').value,
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            document.getElementById('contactForm').style.display = 'none';
            document.getElementById('contactSuccess').style.display = 'block';
        } else {
            errorDiv.textContent = data.error || 'Something went wrong. Please try again.';
            errorDiv.style.display = 'block';
            btn.disabled = false;
            btn.textContent = 'Send Message';
        }
    })
    .catch(() => {
        errorDiv.textContent = 'Something went wrong. Please try again.';
        errorDiv.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Send Message';
    });
}

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
});

// Nav scroll effect
window.addEventListener('scroll', () => {
    const nav = document.querySelector('nav');
    nav.style.background = window.scrollY > 50
        ? 'rgba(10, 22, 40, 0.98)'
        : 'rgba(10, 22, 40, 0.92)';
});
