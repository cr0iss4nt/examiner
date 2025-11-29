import json

def generate_html_from_json(json_data):
    # Упрощённый, безопасный HTML генератор (как в оригинале)
    questions_html = ""
    for i, item in enumerate(json_data, 1):
        q = item.get("question", "")
        answers = item.get("answers", [])
        answers_html = ""
        for answer in answers:
            for text, val in answer.items():
                answers_html += f'''
                <div class="answer">
                    <label>
                        <input type="radio" name="question_{i}" value="{val}">
                        {text}
                    </label>
                </div>
                '''
        questions_html += f'''
        <div class="question">
            <div class="question-text">{i}. {q}</div>
            {answers_html}
        </div>
        '''

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Тест</title>
<style>
body{{font-family:Arial, sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#f5f5f5}}
.question{{background:#fff;border-radius:8px;padding:20px;margin-bottom:20px;box-shadow:0 2px 4px rgba(0,0,0,0.08)}}
.submit-btn{{background:#4CAF50;color:#fff;padding:12px 20px;border:none;border-radius:6px;cursor:pointer}}
.result-info{{display:none;padding:15px;border-radius:8px;margin-top:20px}}
</style>
</head>
<body>
<h1>Тест</h1>
<form id="quizForm">
{questions_html}
<button type="button" class="submit-btn" onclick="checkAnswers()">Проверить ответы</button>
</form>
<div id="result" class="result-info"></div>
<script>
function checkAnswers(){{
  const questions = document.querySelectorAll('.question');
  let correct = 0;
  let total = questions.length;
  let results = [];
  questions.forEach((q, idx)=>{{
    const text = q.querySelector('.question-text').textContent;
    const radios = q.querySelectorAll('input[type=radio]');
    let answered=false, sel='', isCorrect=false;
    radios.forEach(r=>{{ if(r.checked){{ answered=true; sel=r.parentElement.textContent.trim(); if(r.value==='1'){{ isCorrect=true; correct++; }} }} }});
    results.push({{question:text, selectedAnswer: sel, isCorrect, answered}});
  }});
  const percentage = Math.round((correct/total)*100);
  const data = {{timestamp: new Date().toLocaleString(), score: correct, totalQuestions: total, percentage, details: results}};
  document.getElementById('result').style.display='block';
  document.getElementById('result').textContent=`Результат: ${{correct}}/${{total}} (${{percentage}}%)`;
  fetch('/result', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}}).catch(e=>console.error(e));
}}
</script>
</body>
</html>"""
    return html
