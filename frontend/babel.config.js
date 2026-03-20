module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ["babel-preset-expo", { jsxImportSource: "nativewind" }],
    ],
    plugins: [
      // Resolve @/* aliases (e.g. @/lib/supabase → ./lib/supabase)
      [
        "module-resolver",
        {
          root: ["."],
          alias: {
            "@": ".",
          },
        },
      ],
      "react-native-reanimated/plugin",
    ],
  };
};
