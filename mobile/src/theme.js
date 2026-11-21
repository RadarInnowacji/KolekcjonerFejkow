import { Platform } from 'react-native';

// Ten sam język wizualny co demonstrator WWW (inspiracja: nask.pl)
export const C = {
  ink: '#111318',
  ink2: '#2b2f38',
  sub: '#686d78',
  line: '#e6e8ec',
  bg: '#ffffff',
  bg2: '#f5f6f8',
  blue: '#1f4fd6',
  blue2: '#173fb0',
  blueSoft: '#eef2fd',
  green: '#18a058',
  greenNeon: '#2fe08a',
  red: '#d12c3a',
  amber: '#c27a12',
  purple: '#6b2fa0',
  dark: '#05070d',
};

export const F = {
  regular: 'Archivo_400Regular',
  medium: 'Archivo_500Medium',
  semibold: 'Archivo_600SemiBold',
  bold: 'Archivo_700Bold',
  black: 'Archivo_800ExtraBold',
};

export const MONO = Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' });

export const PALETTE = ['#1f4fd6', '#d12c3a', '#18a058', '#e08a12', '#7a3fd0', '#0f8a9a', '#c2407a', '#5a6b10', '#2a9fd6', '#8a5a2b', '#111318', '#e0b400'];
export const campColor = (id, size) => (size === 1 ? '#b8bec9' : PALETTE[id % PALETTE.length]);
