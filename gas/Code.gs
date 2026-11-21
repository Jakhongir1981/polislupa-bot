// PolisLupa — мост между ботом @polislupa_bot и Google Диском.
// Развёрнут как веб-приложение (выполняется от имени владельца). Доступ только с секретным ключом.
const SECRET = '<SECRET в переменных Railway>';
const INBOX_ID = '1gYhXoKJuBUlWL1SVLTMaZKyU07gVpqm4';      // 📥 В Telegram-канал (на одобрение)
const DONE_ID = '1yhM3Ium674XDsEg-vE3aKZsgruhSs21O';       // ✅ Опубликовано
const SHEET_ID = '1flRAXyrS0aszSUm5WHN6bKmBIqFxlAAwOz-anw6sI-s'; // Заявки PolisLupa

function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function doGet(e) {
  if ((e.parameter.key || '') !== SECRET) return out_({error: 'forbidden'});
  if (e.parameter.action === 'list') return out_({files: listInbox_()});
  if (e.parameter.action === 'done') { moveDone_(e.parameter.id); return out_({ok: true}); }
  return out_({ok: true, pong: new Date().toISOString()});
}

function doPost(e) {
  const body = JSON.parse(e.postData.contents || '{}');
  if (body.key !== SECRET) return out_({error: 'forbidden'});
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const name = body.sheet || 'Заявки';
  let sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); if (body.header) sh.appendRow(body.header); }
  sh.appendRow(body.row || []);
  return out_({ok: true});
}

// Медиафайлы в папке «на одобрение». Подпись: текстовый файл с тем же именем (видео.mp4 + видео.txt) или описание файла.
function listInbox_() {
  const folder = DriveApp.getFolderById(INBOX_ID);
  const texts = {}, media = [];
  const it = folder.getFiles();
  while (it.hasNext()) {
    const f = it.next();
    const t = f.getMimeType();
    const base = f.getName().replace(/\.[^.]+$/, '');
    if (t === 'text/plain' || t === 'application/vnd.google-apps.document') {
      texts[base] = t === 'text/plain' ? f.getBlob().getDataAsString('UTF-8') : DocumentApp.openById(f.getId()).getBody().getText();
      texts[base + '#id'] = f.getId();
    } else if (/^(video|image)\//.test(t)) {
      media.push(f);
    }
  }
  return media.map(f => {
    const base = f.getName().replace(/\.[^.]+$/, '');
    if (f.getSharingAccess() !== DriveApp.Access.ANYONE_WITH_LINK) f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    return {id: f.getId(), name: f.getName(), mime: f.getMimeType(), size: f.getSize(),
            caption: texts[base] || f.getDescription() || '', textId: texts[base + '#id'] || null,
            created: f.getDateCreated().toISOString()};
  });
}

function moveDone_(id) {
  const f = DriveApp.getFileById(id);
  f.setSharing(DriveApp.Access.PRIVATE, DriveApp.Permission.NONE);
  f.moveTo(DriveApp.getFolderById(DONE_ID));
  const base = f.getName().replace(/\.[^.]+$/, '');
  const it = DriveApp.getFolderById(INBOX_ID).getFiles();
  while (it.hasNext()) { const t = it.next(); if (t.getName().replace(/\.[^.]+$/, '') === base) t.moveTo(DriveApp.getFolderById(DONE_ID)); }
}
