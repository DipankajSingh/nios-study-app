import React from 'react';
import { View, StyleSheet } from 'react-native';
import MathJax from 'react-native-mathjax';

export default function MathText({ text, className, style, color = '#334155', fontSize = 14 }) {
  if (!text) return null;

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
