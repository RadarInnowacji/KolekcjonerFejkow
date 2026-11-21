import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'ftf_server';
let BASE = 'http://192.168.1.100:8000';

export async function loadServer() {
  try {
    const v = await AsyncStorage.getItem(KEY);
    if (v) BASE = v;
  } catch {}
  return BASE;
}

export async function saveServer(url) {
  let u = (url || '').trim().replace(/\/+$/, '');
  if (u && !/^https?:\/\//i.test(u)) u = 'http://' + u;
  if (u && !/:\d+$/.test(u.replace(/^https?:\/\//, '')) && !u.startsWith('https://')) u += ':8000';
  BASE = u;
  try { await AsyncStorage.setItem(KEY, u); } catch {}
  return u;
}

export const server = () => BASE;
export const thumbUrl = (id) => `${BASE}/api/thumb/${id}`;

async function req(path, body, timeout = 150000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  try {
    const r = await fetch(BASE + path, body === undefined
      ? { signal: ctrl.signal }
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctrl.signal });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.error) throw new Error(j.error || `Błąd serwera ${r.status}`);
    return j;
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Serwer nie odpowiedział na czas.');
    if (String(e.message).includes('Network request failed')) {
      throw new Error(`Brak połączenia z serwerem ${BASE}. Sprawdź adres w Ustawieniach i czy telefon jest w tej samej sieci Wi-Fi.`);
    }
    throw e;
  } finally {
    clearTimeout(t);
  }
}

export const getState = () => req('/api/state', undefined, 15000);
export const getItem = (id) => req(`/api/item/${id}`, undefined, 15000);
export const analyze = (payload) => req('/api/analyze', payload);
export const loadDemo = () => req('/api/demo', {});
export const getJob = (id) => req(`/api/job/${id}`, undefined, 15000);

// Plik z telefonu (obraz lub wideo) → data URL base64, tak jak wysyła strona WWW
export async function fileToDataUrl(uri) {
  const res = await fetch(uri);
  const blob = await res.blob();
  return await new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(fr.result);
    fr.onerror = () => reject(new Error('Nie udało się odczytać pliku'));
    fr.readAsDataURL(blob);
  });
}
