import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, Image, StyleSheet, StatusBar,
  Platform, Linking, Alert, ActivityIndicator, Switch, KeyboardAvoidingView, RefreshControl,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useFonts, Archivo_400Regular, Archivo_500Medium, Archivo_600SemiBold, Archivo_700Bold, Archivo_800ExtraBold } from '@expo-google-fonts/archivo';
import { C, F, campColor } from './src/theme';
import * as API from './src/api';

const TOP = Platform.OS === 'android' ? (StatusBar.currentHeight || 24) : 50;
const CH = { tekst: 'Tekst', wizual: 'Wizual', osoby: 'Osoby', narracja: 'Narracja', domeny: 'Domeny', infrastruktura: 'Infra' };
const REL = { duplikat: 'Duplikat', wariant: 'Wariant', 'powiązanie': 'Powiązanie', 'podobieństwo': 'Podobieństwo' };

export default function App() {
  const [fontsLoaded, fontError] = useFonts({ Archivo_400Regular, Archivo_500Medium, Archivo_600SemiBold, Archivo_700Bold, Archivo_800ExtraBold });
  const [tab, setTab] = useState('analiza');
  const [stack, setStack] = useState([]); // ekrany szczegółów nad zakładką
  const [state, setState] = useState(null);
  const [stateErr, setStateErr] = useState(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setState(await API.getState());
      setStateErr(null);
    } catch (e) {
      setStateErr(e.message);
    }
  }, []);

  useEffect(() => {
    API.loadServer().then(() => { setReady(true); refresh(); });
  }, [refresh]);

  if ((!fontsLoaded && !fontError) || !ready) {
    return <View style={[s.root, { alignItems: 'center', justifyContent: 'center' }]}><ActivityIndicator color={C.blue} /></View>;
  }

  const push = (screen) => setStack((st) => [...st, screen]);
  const pop = () => setStack((st) => st.slice(0, -1));
  const top = stack[stack.length - 1];
  const nav = { push, pop, refresh, state, setTab: (t) => { setStack([]); setTab(t); } };

  return (
    <View style={s.root}>
      <StatusBar barStyle="dark-content" backgroundColor="#fff" />
      <Header online={!!state && !stateErr} onMenu={() => nav.setTab('ustawienia')} />
      <View style={{ flex: 1 }}>
        {top ? (
          top.type === 'result' ? <Result r={top.data} nav={nav} />
            : top.type === 'campaign' ? <Campaign c={top.data} nav={nav} />
              : top.type === 'item' ? <Item id={top.data} nav={nav} /> : null
        ) : tab === 'analiza' ? <Analyze nav={nav} stateErr={stateErr} />
          : tab === 'kampanie' ? <Campaigns nav={nav} err={stateErr} />
            : <Settings nav={nav} err={stateErr} />}
      </View>
      <TabBar tab={top ? null : tab} onTab={nav.setTab} />
    </View>
  );
}

/* ───────────────────────── wspólne ───────────────────────── */

function Header({ online, onMenu }) {
  return (
    <View style={s.header}>
      <Text style={s.wordmark}>FOLLOW<Text style={s.wordmarkThe}> THE </Text>FAKE</Text>
      <TouchableOpacity style={s.pill} onPress={onMenu} activeOpacity={0.7}>
        <View style={[s.dot, { backgroundColor: online ? C.green : C.red }]} />
        <Text style={s.pillText}>{online ? 'Połączono' : 'Serwer'}</Text>
      </TouchableOpacity>
    </View>
  );
}

function TabBar({ tab, onTab }) {
  const items = [['analiza', 'Analiza'], ['kampanie', 'Kampanie'], ['ustawienia', 'Ustawienia']];
  return (
    <View style={s.tabbar}>
      {items.map(([k, l]) => (
        <TouchableOpacity key={k} style={s.tab} onPress={() => onTab(k)} activeOpacity={0.7}>
          <View style={[s.tabLine, tab === k && { backgroundColor: C.blue }]} />
          <Text style={[s.tabText, tab === k && { color: C.blue, fontFamily: F.semibold }]}>{l}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const Btn = ({ title, onPress, kind = 'primary', style, disabled, icon }) => (
  <TouchableOpacity
    onPress={onPress}
    disabled={disabled}
    activeOpacity={0.8}
    style={[s.btn, kind === 'primary' ? s.btnPrimary : kind === 'ghost' ? s.btnGhost : kind === 'red' ? s.btnRed : s.btnLight, disabled && { opacity: 0.5 }, style]}
  >
    <Text style={[s.btnText, kind === 'ghost' && { color: C.blue }, kind === 'light' && { color: '#fff' }]}>{icon ? icon + '  ' : ''}{title}</Text>
  </TouchableOpacity>
);

const Chip = ({ t, kind }) => (
  <View style={[s.chip, kind === 'blue' && s.chipBlue, kind === 'red' && s.chipRed, kind === 'amber' && s.chipAmber]}>
    <Text style={[s.chipText, kind === 'blue' && { color: C.blue2 }, kind === 'red' && { color: '#a11d2a' }, kind === 'amber' && { color: '#8a5508' }]} numberOfLines={1}>{t}</Text>
  </View>
);

const Thumb = ({ id, has, size = 64, label = 'TXT' }) =>
  has ? <Image source={{ uri: API.thumbUrl(id) }} style={{ width: size, height: size, backgroundColor: C.bg2 }} />
    : <View style={{ width: size, height: size, backgroundColor: C.bg2, alignItems: 'center', justifyContent: 'center' }}><Text style={s.thumbLabel}>{label}</Text></View>;

const Back = ({ onPress, label }) => (
  <TouchableOpacity onPress={onPress} style={{ paddingVertical: 12 }} hitSlop={10}>
    <Text style={s.link}>←  {label || 'Wróć'}</Text>
  </TouchableOpacity>
);

function Evidence({ ev, hard }) {
  return (
    <View style={{ marginTop: 6 }}>
      {(ev || []).map((x, i) => {
        const isHard = x.weight >= 0.85 && x.channel !== 'osoby' && x.channel !== 'narracja';
        return (
          <View key={i} style={{ flexDirection: 'row', marginBottom: 4 }}>
            <Text style={{ color: isHard ? C.red : C.blue, width: 16, fontFamily: F.bold }}>{isHard ? '●' : '→'}</Text>
            <Text style={[s.small, { flex: 1, color: C.ink2 }]}>{x.text}</Text>
          </View>
        );
      })}
      {hard && hard.length > 0 && <Text style={[s.small, { color: C.red, marginTop: 2 }]}>Twardy dowód: {hard.join(', ')}</Text>}
    </View>
  );
}

function Channels({ ch }) {
  return (
    <View style={s.channels}>
      {Object.keys(CH).map((k) => {
        const v = ch ? ch[k] : null;
        return (
          <View key={k} style={{ width: '31%', marginBottom: 6 }}>
            <Text style={s.tiny}>{CH[k]} {v == null ? '–' : v.toFixed(2)}</Text>
            <View style={s.track}><View style={[s.fill, { width: `${v == null ? 0 : Math.round(v * 100)}%` }]} /></View>
          </View>
        );
      })}
    </View>
  );
}

function SimRow({ x, nav, hasThumb }) {
  return (
    <TouchableOpacity style={s.sim} activeOpacity={0.7} onPress={() => nav.push({ type: 'item', data: x.id })}>
      <Thumb id={x.id} has={hasThumb} size={60} />
      <View style={{ flex: 1, marginLeft: 12 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          <Text style={[s.simTitle, { flex: 1 }]} numberOfLines={2}>#{x.id} {x.title}</Text>
          <Text style={s.score}>{x.score.toFixed(2)}</Text>
        </View>
        {REL[x.relation] && <View style={{ flexDirection: 'row', marginTop: 4 }}><Chip t={REL[x.relation]} kind={x.relation === 'duplikat' ? 'red' : 'blue'} /></View>}
        <Evidence ev={x.evidence} hard={x.hard} />
        <Channels ch={x.channels} />
      </View>
    </TouchableOpacity>
  );
}

const hasThumb = (state, id) => !!(state && state.items.find((i) => i.id === id && i.thumb));

/* ───────────────────────── Analiza ───────────────────────── */

function Analyze({ nav, stateErr }) {
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]);
  const [net, setNet] = useState(true);
  const [save, setSave] = useState(true);
  const [busy, setBusy] = useState(false);
  const st = nav.state && nav.state.stats;

  const pick = async (kind) => {
    try {
      let r;
      if (kind === 'camera') {
        const p = await ImagePicker.requestCameraPermissionsAsync();
        if (!p.granted) return Alert.alert('Brak dostępu', 'Zezwól aplikacji na użycie aparatu.');
        r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.7 });
      } else {
        r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: kind === 'video' ? ['videos'] : ['images'], quality: 0.8, videoMaxDuration: 60 });
      }
      if (r.canceled || !r.assets?.length) return;
      const a = r.assets[0];
      if (kind === 'video' && a.duration && a.duration > 61000) return Alert.alert('Za długi film', 'Wybierz film do 60 sekund.');
      const isVideo = a.type === 'video' || kind === 'video';
      setFiles((f) => [...f, { uri: a.uri, name: a.fileName || (isVideo ? 'film.mp4' : 'zrzut.jpg'), mime: a.mimeType || (isVideo ? 'video/mp4' : 'image/jpeg'), video: isVideo }]);
    } catch (e) {
      Alert.alert('Nie udało się', e.message);
    }
  };

  const run = async () => {
    if (!url.trim() && !text.trim() && !files.length) return Alert.alert('Brak materiału', 'Dodaj zrzut, film, link albo tekst.');
    setBusy(true);
    try {
      const payload = { url: url.trim(), text: text.trim(), network: net, save, files: [] };
      for (const f of files) payload.files.push({ name: f.name, mime: f.mime, b64: await API.fileToDataUrl(f.uri) });
      const r = await API.analyze(payload);
      r._local = files[0] && !files[0].video ? files[0].uri : null;
      if (save) { setUrl(''); setText(''); setFiles([]); await nav.refresh(); }
      nav.push({ type: 'result', data: r });
    } catch (e) {
      Alert.alert('Analiza nie powiodła się', e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={s.page} keyboardShouldPersistTaps="handled">
        <View style={s.feature}>
          <View style={s.featureGlow} />
          <View style={s.featureTag}><Text style={s.featureTagText}>Wyzwanie NASK · HackNation</Text></View>
          <Text style={s.featureTitle}>Follow the Fake</Text>
          <Text style={s.featureText}>Sprawdź, czy reklama należy do znanej kampanii oszustów. Każde powiązanie dostaje uzasadnienie.</Text>
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 18 }}>
            <Btn title="Zrzut ekranu" onPress={() => pick('image')} style={{ flex: 1 }} />
            <Btn title="Film" kind="light" onPress={() => pick('video')} style={{ flex: 1, borderWidth: 1.5, borderColor: 'rgba(255,255,255,.8)', backgroundColor: 'transparent' }} />
          </View>
        </View>

        {stateErr ? (
          <TouchableOpacity style={s.notice} onPress={() => nav.setTab('ustawienia')}>
            <Text style={s.noticeTitle}>Brak połączenia z serwerem</Text>
            <Text style={s.small}>Ustaw adres komputera, na którym działa Follow the Fake →</Text>
          </TouchableOpacity>
        ) : st ? (
          <View style={s.stats}>
            {[[st.materials, 'materiałów'], [st.campaigns, 'kampanii'], [st.links, 'powiązań']].map(([n, l], i) => (
              <View key={l} style={[s.stat, i > 0 && { borderLeftWidth: 1, borderLeftColor: C.line, paddingLeft: 14 }]}>
                <Text style={s.statN}>{n}</Text><Text style={s.small}>{l}</Text>
              </View>
            ))}
          </View>
        ) : null}

        <Text style={s.h2}>Nowy materiał</Text>
        {files.length > 0 && (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
            {files.map((f, i) => (
              <TouchableOpacity key={i} onPress={() => setFiles(files.filter((_, j) => j !== i))}>
                {f.video ? <View style={[s.fileTile, { backgroundColor: C.ink }]}><Text style={{ color: '#fff', fontFamily: F.bold }}>FILM</Text></View>
                  : <Image source={{ uri: f.uri }} style={s.fileTile} />}
                <Text style={[s.tiny, { textAlign: 'center' }]}>usuń ✕</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        <View style={{ flexDirection: 'row', gap: 10, marginBottom: 14 }}>
          <Btn title="Aparat" kind="ghost" onPress={() => pick('camera')} style={{ flex: 1 }} />
          <Btn title="Galeria" kind="ghost" onPress={() => pick('image')} style={{ flex: 1 }} />
        </View>
        <Text style={s.label}>Adres URL reklamy lub strony</Text>
        <TextInput style={s.input} value={url} onChangeText={setUrl} placeholder="https://…" placeholderTextColor={C.sub} autoCapitalize="none" autoCorrect={false} keyboardType="url" />
        <Text style={s.label}>Tekst / wskazówka</Text>
        <TextInput style={[s.input, { minHeight: 110, textAlignVertical: 'top' }]} value={text} onChangeText={setText} multiline placeholder="Treść reklamy, SMS, log rozmowy, nazwa produktu…" placeholderTextColor={C.sub} />
        <View style={s.switchRow}><Text style={[s.body, { flex: 1 }]}>Pobieraj metadane domen (przekierowania, RDAP, DNS)</Text><Switch value={net} onValueChange={setNet} trackColor={{ true: C.blue }} /></View>
        <View style={s.switchRow}><Text style={[s.body, { flex: 1 }]}>Dodaj materiał do zbioru</Text><Switch value={save} onValueChange={setSave} trackColor={{ true: C.blue }} /></View>
        <Btn title={busy ? 'Analizuję…' : 'Analizuj'} onPress={run} disabled={busy} style={{ marginTop: 16 }} />
        {busy && <Text style={[s.small, { textAlign: 'center', marginTop: 10 }]}>Wyodrębniam cechy{net ? ', sprawdzam domeny' : ''} i porównuję ze zbiorem…</Text>}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

/* ───────────────────────── Wynik ───────────────────────── */

function Result({ r, nav }) {
  const code = r.final_campaign_code || r.campaign_code;
  const kind = r.decision === 'nowy wzorzec' ? 'new' : r.decision === 'duplikat' ? 'dup' : 'known';
  const bg = kind === 'new' ? '#0f7a45' : kind === 'dup' ? C.purple : C.blue;
  const head = kind === 'new' ? 'Nowy wzorzec' : kind === 'dup' ? `Duplikat materiału #${r.duplicate_of}` : 'Znana kampania';
  const m = r.material || {};
  const camp = nav.state && r.final_campaign != null ? nav.state.campaigns.find((c) => c.id === r.final_campaign) : null;
  const conf = Math.round((r.confidence || 0) * 100);
  return (
    <ScrollView contentContainerStyle={s.page}>
      <Back onPress={nav.pop} label="Nowa analiza" />
      <View style={[s.verdict, { backgroundColor: bg }]}>
        {r._local ? <Image source={{ uri: r._local }} style={{ width: 64, height: 64, marginRight: 14 }} /> : null}
        <View style={{ flex: 1 }}>
          <Text style={s.verdictTitle}>{head}</Text>
          <Text style={s.verdictText}>{r.reason}</Text>
        </View>
        {code ? <View style={s.codePill}><Text style={s.codeText}>{code}</Text></View> : null}
      </View>
      <View style={s.card}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={s.bodyB}>Pewność decyzji</Text><Text style={s.bodyB}>{conf}%</Text></View>
        <View style={[s.track, { height: 6, marginTop: 8 }]}><View style={[s.fill, { width: `${conf}%` }]} /></View>
        {r.campaign_name ? <Text style={[s.small, { marginTop: 12 }]}>Kampania: <Text style={{ color: C.ink, fontFamily: F.semibold }}>{r.campaign_name}</Text></Text> : null}
        {camp && camp.size > 1 && (
          <TouchableOpacity onPress={() => nav.push({ type: 'campaign', data: camp })} style={{ marginTop: 8 }}>
            <Text style={s.link}>Zobacz kampanię {camp.code} ({camp.size} materiałów) →</Text>
          </TouchableOpacity>
        )}
      </View>

      <Text style={s.h2}>Najbardziej podobne incydenty</Text>
      {r.similar && r.similar.length ? r.similar.map((x) => <SimRow key={x.id} x={x} nav={nav} hasThumb={hasThumb(nav.state, x.id)} />)
        : <Text style={s.body}>Brak podobnych materiałów w zbiorze.</Text>}

      <Text style={s.h2}>Wyodrębnione cechy</Text>
      <Features m={m} />

      {kind !== 'new' || (m.narrative && m.narrative.manipulation && m.narrative.manipulation.length) ? (
        <Btn title="Zgłoś do CERT Polska  ↗" kind="red" onPress={() => Linking.openURL('https://incydent.cert.pl')} style={{ marginTop: 22 }} />
      ) : null}
    </ScrollView>
  );
}

function Features({ m }) {
  if (!m || !m.narrative) return null;
  const rows = [
    ['Wizerunki osób', m.entities.persons, 'blue'],
    ['Marki / logotypy', m.entities.brands],
    ['Podszywanie się', m.entities.impersonation, 'red'],
    ['Tematy', m.narrative.topics, 'blue'],
    ['Chwyty manipulacyjne', m.narrative.manipulation, 'amber'],
    ['Domeny', m.infra.domains, 'amber'],
    ['Trackery', m.infra.trackers, 'red'],
    ['Serwery DNS', m.infra.nameservers],
    ['Słowa kluczowe', m.narrative.keywords.slice(0, 8)],
  ];
  return (
    <View style={s.card}>
      {rows.map(([k, arr, kind]) => (
        <View key={k} style={{ marginBottom: 10 }}>
          <Text style={s.tinyCaps}>{k}</Text>
          {arr && arr.length ? (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>{arr.map((x) => <Chip key={x} t={x} kind={kind} />)}</View>
          ) : <Text style={s.small}>—</Text>}
        </View>
      ))}
      {m.quality && (
        <>
          <Text style={s.tinyCaps}>Kompletność danych</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
            {Object.entries(m.quality.channels).map(([k, ok]) => <Chip key={k} t={`${ok ? '✓' : '✕'} ${k}`} kind={ok ? 'blue' : undefined} />)}
          </View>
        </>
      )}
    </View>
  );
}

/* ───────────────────────── Kampanie ───────────────────────── */

function Campaigns({ nav, err }) {
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const st = nav.state;
  const onRefresh = async () => { setRefreshing(true); await nav.refresh(); setRefreshing(false); };
  const demo = async () => {
    setBusy(true);
    try {
      const j = await API.loadDemo();
      for (let i = 0; i < 90; i++) {
        const s2 = await API.getJob(j.id);
        if (s2.finished) break;
        await new Promise((r) => setTimeout(r, 1000));
      }
      await nav.refresh();
    } catch (e) { Alert.alert('Błąd', e.message); }
    setBusy(false);
  };
  const camps = st ? st.campaigns : [];
  return (
    <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      <Text style={s.h1}>Kampanie</Text>
      <Text style={[s.body, { marginBottom: 18 }]}>Grupy reklam połączonych wspólnymi śladami: wizerunkiem, narracją, kreacją, domenami i infrastrukturą.</Text>
      {err ? <Text style={s.body}>{err}</Text> : !camps.length ? (
        <View style={s.empty}>
          <Text style={[s.body, { textAlign: 'center', marginBottom: 14 }]}>Zbiór jest pusty.</Text>
          <Btn title={busy ? 'Wczytuję…' : 'Wczytaj zbiór demonstracyjny'} onPress={demo} disabled={busy} />
        </View>
      ) : camps.map((c) => {
        const thumbId = c.members.find((id) => hasThumb(st, id));
        return (
          <TouchableOpacity key={c.id} style={s.news} activeOpacity={0.7} onPress={() => nav.push({ type: 'campaign', data: c })}>
            <View>
              {thumbId ? <Image source={{ uri: API.thumbUrl(thumbId) }} style={s.newsImg} /> : <View style={[s.newsImg, { backgroundColor: campColor(c.id, c.size) }]} />}
              <View style={s.newsCode}><Text style={s.newsCodeText}>{c.code}</Text></View>
            </View>
            <View style={{ flex: 1, marginLeft: 14 }}>
              <Text style={s.cat}>▤  {c.size > 1 ? 'Kampania' : 'Pojedynczy materiał'}</Text>
              <Text style={s.meta}>{c.first_seen ? c.first_seen.split('-').reverse().join('.') + '  |  ' : ''}{c.size} mat.</Text>
              <Text style={s.newsTitle} numberOfLines={3}>{c.name}</Text>
              <Text style={[s.link, { marginTop: 6 }]}>Zobacz →</Text>
            </View>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

function Campaign({ c, nav }) {
  const items = nav.state ? nav.state.items.filter((i) => i.campaign === c.id) : [];
  const row = (k, arr, kind) => arr && arr.length ? (
    <View style={{ marginBottom: 12 }}>
      <Text style={s.tinyCaps}>{k}</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>{arr.map(([v, n]) => <Chip key={v} t={`${v} ·${n}`} kind={kind} />)}</View>
    </View>
  ) : null;
  return (
    <ScrollView contentContainerStyle={s.page}>
      <Back onPress={nav.pop} />
      <Text style={[s.cat, { marginBottom: 4 }]}>▤  {c.code} · spójność {c.cohesion.toFixed(2)}</Text>
      <Text style={s.h1}>{c.name}</Text>
      <Text style={[s.body, { marginBottom: 16 }]}>{c.size} materiałów{c.first_seen ? ` · ${c.first_seen} → ${c.last_seen}` : ''}{c.duplicates ? ` · duplikaty: ${c.duplicates}` : ''}</Text>
      <View style={s.card}>
        {row('Wizerunki', c.persons, 'blue')}
        {row('Tematy', c.topics)}
        {row('Chwyty', c.manipulation, 'amber')}
        {row('Domeny', c.domains, 'amber')}
        {row('Trackery', c.trackers, 'red')}
        {row('Przesłanki (kanały)', c.evidence_types.map(([k, n]) => [CH[k] || k, n]))}
      </View>
      <Text style={s.h2}>Materiały</Text>
      {items.map((i) => (
        <TouchableOpacity key={i.id} style={s.sim} onPress={() => nav.push({ type: 'item', data: i.id })} activeOpacity={0.7}>
          <Thumb id={i.id} has={i.thumb} size={56} />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={s.simTitle} numberOfLines={2}>#{i.id} {i.title}</Text>
            <Text style={s.small} numberOfLines={1}>{i.date} · {i.domains.join(', ')}</Text>
          </View>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

function Item({ id, nav }) {
  const [it, setIt] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { API.getItem(id).then(setIt).catch((e) => setErr(e.message)); }, [id]);
  if (err) return <View style={s.page}><Back onPress={nav.pop} /><Text style={s.body}>{err}</Text></View>;
  if (!it) return <View style={[s.page, { alignItems: 'center' }]}><ActivityIndicator color={C.blue} style={{ marginTop: 40 }} /></View>;
  return (
    <ScrollView contentContainerStyle={s.page}>
      <Back onPress={nav.pop} />
      <Text style={s.cat}>▤  Materiał #{id}</Text>
      <Text style={[s.h1, { fontSize: 22, lineHeight: 28 }]}>{it.title}</Text>
      {it.thumb ? <Image source={{ uri: it.thumb }} style={{ width: '100%', aspectRatio: 1, resizeMode: 'contain', backgroundColor: C.bg2, marginVertical: 12 }} /> : null}
      {it.text ? <Text style={[s.small, { backgroundColor: C.bg2, padding: 12, color: C.ink2 }]} numberOfLines={10}>{it.text}</Text> : null}
      <Text style={s.h2}>Powiązane materiały</Text>
      {it.neighbors.length ? it.neighbors.map((x) => <SimRow key={x.id} x={x} nav={nav} hasThumb={hasThumb(nav.state, x.id)} />)
        : <Text style={s.body}>Brak powiązań powyżej progu.</Text>}
      <Text style={s.h2}>Cechy</Text>
      <Features m={it} />
    </ScrollView>
  );
}

/* ───────────────────────── Ustawienia ───────────────────────── */

function Settings({ nav, err }) {
  const [url, setUrl] = useState(API.server());
  const [busy, setBusy] = useState(false);
  const test = async () => {
    setBusy(true);
    const u = await API.saveServer(url);
    setUrl(u);
    await nav.refresh();
    setBusy(false);
  };
  const caps = nav.state && nav.state.capabilities;
  return (
    <ScrollView contentContainerStyle={s.page} keyboardShouldPersistTaps="handled">
      <Text style={s.h1}>Ustawienia</Text>
      <Text style={s.label}>Adres serwera Follow the Fake</Text>
      <TextInput style={s.input} value={url} onChangeText={setUrl} autoCapitalize="none" autoCorrect={false} placeholder="http://192.168.1.23:8000" placeholderTextColor={C.sub} />
      <Btn title={busy ? 'Sprawdzam…' : 'Zapisz i sprawdź połączenie'} onPress={test} disabled={busy} style={{ marginTop: 12 }} />
      <View style={[s.notice, { marginTop: 16, borderLeftColor: err ? C.red : C.green }]}>
        <Text style={s.noticeTitle}>{err ? 'Brak połączenia' : 'Połączono z serwerem'}</Text>
        <Text style={s.small}>{err || `${API.server()} · ${nav.state ? nav.state.stats.materials : 0} materiałów w zbiorze`}</Text>
      </View>
      {caps && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
          <Chip t={`${caps.ocr ? '✓' : '–'} OCR`} kind={caps.ocr ? 'blue' : undefined} />
          <Chip t={`${caps.opencv ? '✓' : '–'} QR / wideo`} kind={caps.opencv ? 'blue' : undefined} />
          <Chip t={`${caps.faces.detector ? '✓' : '–'} twarze`} kind={caps.faces.detector ? 'blue' : undefined} />
          <Chip t={`${caps.meta_token ? '✓' : '–'} Meta Ad Library`} kind={caps.meta_token ? 'blue' : undefined} />
        </View>
      )}
      <Text style={s.h2}>Jak połączyć</Text>
      <Text style={s.body}>1. Na komputerze uruchom Follow the Fake (START.bat).{'\n'}2. Sprawdź IP komputera: w wierszu poleceń wpisz ipconfig i znajdź „Adres IPv4”.{'\n'}3. Wpisz tu http://TWOJE-IP:8000. Telefon i komputer muszą być w tej samej sieci Wi-Fi.{'\n'}4. Jeśli serwer działa w internecie, wpisz jego adres https://…</Text>
      <Text style={[s.small, { marginTop: 24 }]}>Projekt zespołu startującego w HackNation – wyzwanie „Kolekcjoner fejków / Follow the Fake”. Nie jest oficjalnym narzędziem NASK ani CERT Polska.</Text>
    </ScrollView>
  );
}

/* ───────────────────────── style ───────────────────────── */

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  page: { padding: 20, paddingBottom: 60 },
  header: { paddingTop: TOP + 8, paddingBottom: 12, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: C.line, backgroundColor: '#fff' },
  wordmark: { fontFamily: F.black, fontSize: 21, color: C.ink, letterSpacing: -0.5 },
  wordmarkThe: { fontFamily: F.medium, fontSize: 12, color: C.blue, letterSpacing: 1 },
  pill: { flexDirection: 'row', alignItems: 'center', borderWidth: 1.5, borderColor: C.blue, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 },
  pillText: { fontFamily: F.medium, color: C.blue, fontSize: 14 },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 7 },
  tabbar: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.line, backgroundColor: '#fff', paddingBottom: Platform.OS === 'ios' ? 24 : 8 },
  tab: { flex: 1, alignItems: 'center', paddingTop: 0 },
  tabLine: { height: 2, width: '60%', backgroundColor: 'transparent', marginBottom: 10 },
  tabText: { fontFamily: F.medium, fontSize: 15, color: C.ink },

  feature: { backgroundColor: C.dark, padding: 22, paddingTop: 70, overflow: 'hidden', marginBottom: 18 },
  featureGlow: { position: 'absolute', right: -80, top: -80, width: 260, height: 260, borderRadius: 130, backgroundColor: 'rgba(42,91,255,0.45)' },
  featureTag: { alignSelf: 'flex-start', backgroundColor: C.greenNeon, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  featureTagText: { fontFamily: F.bold, fontSize: 12, color: '#05140c' },
  featureTitle: { fontFamily: F.black, fontSize: 38, color: '#fff', letterSpacing: -1.2, marginTop: 12, lineHeight: 42 },
  featureText: { fontFamily: F.regular, fontSize: 15.5, color: '#d9def0', lineHeight: 22, marginTop: 8 },

  stats: { flexDirection: 'row', borderTopWidth: 1, borderBottomWidth: 1, borderColor: C.line, paddingVertical: 14, marginBottom: 8 },
  stat: { flex: 1 },
  statN: { fontFamily: F.black, fontSize: 28, color: C.ink, letterSpacing: -1 },

  h1: { fontFamily: F.black, fontSize: 30, color: C.ink, letterSpacing: -0.8, lineHeight: 36, marginBottom: 6 },
  h2: { fontFamily: F.bold, fontSize: 21, color: C.ink, letterSpacing: -0.3, marginTop: 26, marginBottom: 12 },
  body: { fontFamily: F.regular, fontSize: 15.5, color: C.sub, lineHeight: 23 },
  bodyB: { fontFamily: F.semibold, fontSize: 15, color: C.ink },
  small: { fontFamily: F.regular, fontSize: 13.5, color: C.sub, lineHeight: 19 },
  tiny: { fontFamily: F.regular, fontSize: 11, color: C.sub },
  tinyCaps: { fontFamily: F.bold, fontSize: 11.5, color: C.sub, letterSpacing: 0.8, textTransform: 'uppercase' },
  label: { fontFamily: F.semibold, fontSize: 14.5, color: C.ink, marginTop: 14, marginBottom: 7 },
  link: { fontFamily: F.medium, fontSize: 15.5, color: C.blue },
  input: { borderWidth: 1.5, borderColor: '#d6d9df', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontFamily: F.regular, fontSize: 15.5, color: C.ink, backgroundColor: '#fff' },
  switchRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12, gap: 12 },

  btn: { borderRadius: 999, paddingVertical: 14, paddingHorizontal: 18, alignItems: 'center' },
  btnPrimary: { backgroundColor: C.blue },
  btnGhost: { backgroundColor: '#fff', borderWidth: 1.5, borderColor: C.blue },
  btnRed: { backgroundColor: C.red },
  btnLight: { backgroundColor: 'transparent' },
  btnText: { fontFamily: F.semibold, fontSize: 15.5, color: '#fff' },

  chip: { backgroundColor: C.bg2, borderWidth: 1, borderColor: C.line, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3, maxWidth: '100%' },
  chipBlue: { backgroundColor: C.blueSoft, borderColor: '#d3ddfa' },
  chipRed: { backgroundColor: '#fdeced', borderColor: '#f6c9cd' },
  chipAmber: { backgroundColor: '#fdf4e4', borderColor: '#f2ddb4' },
  chipText: { fontFamily: F.regular, fontSize: 12.5, color: C.ink2 },

  notice: { backgroundColor: C.bg2, borderLeftWidth: 4, borderLeftColor: C.blue, padding: 14, marginBottom: 8 },
  noticeTitle: { fontFamily: F.semibold, fontSize: 15, color: C.ink, marginBottom: 2 },
  card: { borderWidth: 1, borderColor: C.line, padding: 16, backgroundColor: '#fff' },
  empty: { backgroundColor: C.bg2, padding: 24 },
  fileTile: { width: 72, height: 72, alignItems: 'center', justifyContent: 'center', backgroundColor: C.bg2 },
  thumbLabel: { fontFamily: F.bold, fontSize: 11, color: C.sub },

  verdict: { flexDirection: 'row', alignItems: 'center', padding: 18 },
  verdictTitle: { fontFamily: F.black, fontSize: 22, color: '#fff', letterSpacing: -0.3 },
  verdictText: { fontFamily: F.regular, fontSize: 13.5, color: 'rgba(255,255,255,.88)', marginTop: 4, lineHeight: 19 },
  codePill: { backgroundColor: '#fff', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5, marginLeft: 10 },
  codeText: { fontFamily: F.black, fontSize: 15, color: C.ink },
  track: { height: 4, backgroundColor: '#e9ebef', borderRadius: 2, overflow: 'hidden', marginTop: 3 },
  fill: { height: '100%', backgroundColor: C.blue, borderRadius: 2 },
  sim: { flexDirection: 'row', paddingVertical: 14, borderTopWidth: 1, borderTopColor: C.line },
  simTitle: { fontFamily: F.semibold, fontSize: 15, color: C.blue, lineHeight: 20 },
  score: { fontFamily: F.black, fontSize: 19, color: C.ink, marginLeft: 8 },
  channels: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', marginTop: 8 },

  news: { flexDirection: 'row', paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: C.line },
  newsImg: { width: 118, height: 96, backgroundColor: C.bg2 },
  newsCode: { position: 'absolute', left: 6, bottom: 6, backgroundColor: 'rgba(0,0,0,.72)', paddingHorizontal: 6, paddingVertical: 2 },
  newsCodeText: { fontFamily: F.bold, fontSize: 11, color: '#fff' },
  cat: { fontFamily: F.medium, fontSize: 14.5, color: C.blue },
  meta: { fontFamily: F.regular, fontSize: 13.5, color: C.sub, marginVertical: 3 },
  newsTitle: { fontFamily: F.medium, fontSize: 16.5, color: C.ink, lineHeight: 22 },
});
