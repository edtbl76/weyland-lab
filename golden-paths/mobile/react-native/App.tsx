// Root component. Renders <Hello/> (the demo greeting `hello, weyland`) inside the app shell.
// Default-exported so index.js can register it with Expo for native + web.
import { StatusBar } from 'expo-status-bar';
import { SafeAreaView } from 'react-native';
import { Hello } from './src/Hello';

export default function App() {
  return (
    <SafeAreaView style={{ flex: 1 }}>
      <Hello />
      <StatusBar style="auto" />
    </SafeAreaView>
  );
}
