import React from 'react';
import { View, StyleSheet, Platform, Text } from 'react-native';
import MathJax from 'react-native-mathjax';

let Latex = null;
if (Platform.OS === 'web') {
  Latex = require('react-latex-next').default;
  require('katex/dist/katex.min.css');
}

export default function MathText({ text, className, style, color = '#334155', fontSize = 14 }) {
  if (!text) return null;

  if (Platform.OS === 'web' && Latex) {
    return (
      <View className={className} style={[styles.container, style]}>
        <Text style={{ fontSize, color, lineHeight: fontSize * 1.5, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" }}>
          <Latex>{text}</Latex>
        </Text>
      </View>
    );
  }

  const html = `
    <div style="font-family: -apple-system, system-ui, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, sans-serif; font-size: ${fontSize}px; color: ${color}; line-height: 1.5; margin: 0; padding: 0; word-wrap: break-word;">
      ${String(text).replace(/\n/g, '<br/>')}
    </div>
  `;

  return (
    <View className={className} style={[styles.container, style]}>
      <MathJax 
        html={html}
        mathJaxOptions={{ messageStyle: 'none' }}
        style={{ backgroundColor: 'transparent' }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 0,
    margin: 0
  }
});
