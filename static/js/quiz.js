(function () {
    'use strict';

    var form = document.getElementById('quiz-form');
    var timerEl = document.getElementById('quiz-timer');
    var timeLeft = parseInt(document.getElementById('quiz-time-left').getAttribute('data-seconds'), 10) || 600;
    var timerInterval = null;
    var submitted = false;

    function formatTime(seconds) {
        var m = Math.floor(seconds / 60);
        var s = seconds % 60;
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    function updateTimer() {
        if (submitted) return;
        timeLeft--;
        if (timerEl) {
            timerEl.textContent = 'الوقت المتبقي: ' + formatTime(timeLeft);
            timerEl.classList.remove('warning', 'danger');
            if (timeLeft <= 60) timerEl.classList.add('danger');
            else if (timeLeft <= 120) timerEl.classList.add('warning');
        }
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            if (form && !submitted) form.submit();
        }
    }

    if (timerEl && timeLeft > 0) {
        timerEl.textContent = 'الوقت المتبقي: ' + formatTime(timeLeft);
        timerInterval = setInterval(updateTimer, 1000);
    }

    // Prevent refresh/back during quiz (anti-cheat)
    if (form) {
        window.addEventListener('beforeunload', function (e) {
            if (!submitted && form.querySelector('input[type="radio"]:checked')) {
                e.preventDefault();
            }
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            if (submitted) return;
            submitted = true;
            if (timerInterval) clearInterval(timerInterval);

            var quizSessionId = document.getElementById('quiz-session-id').value;
            var answers = {};
            form.querySelectorAll('input[name^="q_"]:checked').forEach(function (input) {
                var qId = input.name.replace('q_', '');
                answers[qId] = input.value;
            });

            fetch(form.action, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    quiz_session_id: quizSessionId,
                    answers: answers
                })
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        showResults(data);
                    } else {
                        alert(data.error || 'فشل الإرسال.');
                        submitted = false;
                    }
                })
                .catch(function () {
                    alert('خطأ في الشبكة. حاول مرة أخرى.');
                    submitted = false;
                });
        });
    }

    function showResults(data) {
        var container = document.getElementById('quiz-questions-container');
        if (!container) return;

        var totalPossible = data.total_possible || 0;
        var resultsHtml = '<div class="result-summary card"><p class="score">نتيجتك: ' + data.total_score + ' / ' + totalPossible + ' نقطة</p></div>';

        (data.results || []).forEach(function (r) {
            var block = document.querySelector('.question-block[data-question-id="' + r.question_id + '"]');
            if (!block) return;
            var opts = block.querySelectorAll('.options label');
            opts.forEach(function (label) {
                var val = label.querySelector('input') && label.querySelector('input').value;
                label.classList.remove('correct', 'wrong');
                label.querySelector('input').disabled = true;
                if (val === r.correct_answer) label.classList.add('correct');
                if (val === r.selected && !r.is_correct) label.classList.add('wrong');
            });
        });

        container.insertAdjacentHTML('afterbegin', resultsHtml);
        document.getElementById('quiz-timer').style.display = 'none';
        var submitBtn = form && form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.style.display = 'none';

        // Scroll to top to show score
        window.scrollTo(0, 0);
    }
})();
