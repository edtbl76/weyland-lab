// Expo's Babel preset — required so Metro (bundle smoke) and jest-expo (tests) transform the RN/TSX
// source. This is the Expo-standard config; do not replace with a bare @babel/preset-* set.
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
  };
};
