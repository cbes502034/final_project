/* ============================================================
   docs.js — 說明文件共用的行為

   目前只做一件事：讓側欄的章節跳轉不要污染瀏覽器歷史。

   為什麼要這樣做
   ------------------------------------------------------------
   瀏覽器預設會把每一次 #錨點 跳轉都存成一筆歷史紀錄。
   讀者在文件裡點過十個章節，就累積了十筆，
   想回到進來之前的頁面（例如系統本身）要按十次「上一頁」。

   改成 history.replaceState 之後，跳轉只會「換掉」目前這一筆，
   不會新增。所以不管在文件裡跳幾次，
   **按一次上一頁就回到進來之前的地方**。
   ============================================================ */
(function () {
  'use strict';

  var reduced = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
    if (!a) return;

    // 新分頁開啟、或按著 Ctrl / Cmd 點的，交給瀏覽器自己處理
    if (a.target === '_blank' || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;

    var id = a.getAttribute('href').slice(1);
    if (!id) return;

    // 找不到對應的區塊就不要攔截。
    // 心智圖的分享連結長得像 #mindmap&who=...，會走到這裡，
    // 交還給瀏覽器預設行為才不會壞掉。
    var target = document.getElementById(id);
    if (!target) return;

    e.preventDefault();
    target.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });

    // 換掉網址列但不新增歷史紀錄。
    // 這一行就是整個檔案的重點。
    try {
      history.replaceState(null, '', '#' + id);
    } catch (err) {
      /* 用 file:// 直接開的時候某些瀏覽器會擋，忽略就好，捲動已經完成了 */
    }
  });
})();
