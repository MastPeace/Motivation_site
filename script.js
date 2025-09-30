// Вычисление индекса цитаты на текущий день
function getQuoteOfTheDay() {
  // Часовой пояс МСК (UTC+3)
  const now = new Date();
  const utcHour = now.getUTCHours();
  // Смещаем время на +3 для Москвы, потом вычисляем дату
  now.setUTCHours(utcHour + 3);
  const daySeed = now.getFullYear() * 1000 + now.getMonth() * 50 + now.getDate();
  // Псевдослучайный индекс по дню
  const index = daySeed % quotes.length;
  return quotes[index];
}

function renderQuote() {
  const quote = getQuoteOfTheDay();
  document.getElementById('quote-text').innerText = quote.text;
  document.getElementById('quote-author').innerText = quote.author;
  document.getElementById('quote-image').src = quote.image;
  document.getElementById('quote-image').alt = `Мотивирующая картинка: ${quote.text}`;
  document.getElementById('quote-source').href = quote.source;
  document.getElementById('quote-source').innerText = quote.source.replace(/https?:\/\//, "");
}

renderQuote();

// Если страница открыта дольше суток — автообновление в 00:00 МСК
function scheduleNextUpdate() {
  const now = new Date();
  // Перевести в московское время
  const mskNow = new Date(now.getTime() + (3 - now.getTimezoneOffset() / 60) * 60 * 60 * 1000);
  mskNow.setHours(0,0,0,0);
  const nextMidnight = mskNow.getTime() + 24 * 60 * 60 * 1000;
  setTimeout(() => { location.reload(); }, nextMidnight - Date.now());
}
scheduleNextUpdate();
