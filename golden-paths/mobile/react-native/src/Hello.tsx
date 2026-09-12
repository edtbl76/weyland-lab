// Golden path — Mobile/React Native (Expo) (B164). The demo component the app renders and the lane
// tests. A mobile app is a CLIENT, so the known payload `hello, weyland` is rendered on-screen (the
// /hello-equivalent) rather than served over HTTP. `golden-react-native` is the service-name token.
import { Text, View, StyleSheet } from 'react-native';

export const SERVICE_NAME = 'golden-react-native';

export function Hello({ name = 'weyland' }: { name?: string }) {
  return (
    <View style={styles.container}>
      <Text accessibilityRole="header" testID="greeting">
        hello, {name}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
