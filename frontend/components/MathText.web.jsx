import React from 'react';
import { View } from 'react-native';
import 'katex/dist/katex.min.css';
import Latex from 'react-latex-next';

export default function MathText({ text, className, style, color = '#334155', fontSize = 14 }) {
  if (!text) return null;

  return (
    <View className={className} style={[{ color, fontSize }, style]}>
      <Latex>{String(text)}</Latex>
    </View>
  );
}
