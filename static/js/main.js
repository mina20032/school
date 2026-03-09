(function () {
    'use strict';

    // Close flash messages on click
    document.querySelectorAll('.alert').forEach(function (el) {
        el.addEventListener('click', function () {
            this.style.display = 'none';
        });
    });

    // Confirm delete
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(this.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });
})();
