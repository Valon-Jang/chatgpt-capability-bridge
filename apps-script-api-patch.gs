// Replace the old doGet() with this API version, then add doPost() and postMessageOutput_().
// Keep the rest of the existing Code.gs functions unchanged.

function doGet(e) {
  const p = (e && e.parameter) ? e.parameter : {};
  const action = String(p.action || 'state');
  const prefix = String(p.prefix || '');
  let result;

  try {
    if (action !== 'state') {
      throw new Error('지원하지 않는 조회입니다.');
    }
    result = getInitialState(p.name || '');
  } catch (err) {
    result = fail_(errorMessage_(err));
  }

  if (/^[A-Za-z_$][0-9A-Za-z_$]*$/.test(prefix)) {
    return ContentService
      .createTextOutput(prefix + '(' + JSON.stringify(result) + ');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }

  return ContentService
    .createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const p = (e && e.parameter) ? e.parameter : {};
  const action = String(p.action || '');
  const requestId = String(p.requestId || '');
  let result;

  try {
    if (action === 'proposal') {
      result = submitProposal(p.name || '', p.candidate || '');
    } else if (action === 'vote') {
      let ids = [];
      try {
        ids = JSON.parse(p.candidateIds || '[]');
      } catch (_) {
        ids = [];
      }
      result = saveVote(p.name || '', ids);
    } else {
      result = fail_('지원하지 않는 요청입니다.');
    }
  } catch (err) {
    result = fail_(errorMessage_(err));
  }

  return postMessageOutput_(requestId, result);
}

function postMessageOutput_(requestId, response) {
  const payload = JSON.stringify({
    source: 'naming-api',
    requestId: requestId,
    response: response
  });

  const payloadString = JSON.stringify(payload)
    .replace(/</g, '\\u003c')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');

  return HtmlService.createHtmlOutput(
    '<!doctype html><meta charset="utf-8">' +
    '<script>' +
    'parent.postMessage(JSON.parse(' + payloadString + '), "https://valon-jang.github.io");' +
    '<\\/script>'
  );
}
