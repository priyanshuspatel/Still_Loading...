# macOS launchd Background Services

These Property List (`.plist`) templates configure macOS `launchd` to run *Still Loading...* background daemons automatically without requiring an active terminal window.

---

## 1. Battery Telemetry Agent (`com.stillloading.battery.plist`)

Streams your MacBook's real-time battery status (`pmset -g batt`) to the Arduino UNO Q over local Wi-Fi every 15 seconds.

### Installation
1. Edit `mac-agent/launchd/com.stillloading.battery.plist` and replace `REPLACE_WITH_REPO_DIR` with the absolute path to this repository (e.g. `/Users/yourname/still-loading`).
2. Copy the plist into your user's LaunchAgents directory:
   ```bash
   cp mac-agent/launchd/com.stillloading.battery.plist ~/Library/LaunchAgents/
   ```
3. Load and start the agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.stillloading.battery.plist
   ```
4. Verify execution:
   ```bash
   launchctl list | grep stillloading
   tail -f /tmp/still-loading-battery.log
   ```
5. To stop and uninstall:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.stillloading.battery.plist
   rm ~/Library/LaunchAgents/com.stillloading.battery.plist
   ```

---

## 2. Telemetry Relay Daemon (`com.stillloading.relay.plist`)

Runs `relay/telemetry_relay.py` on `127.0.0.1:8765`, enabling the web dashboard (`stillloading.tech` or `localhost:5173`) to display live physical hardware state and failure intelligence.

### Installation
1. Edit `mac-agent/launchd/com.stillloading.relay.plist`:
   - Replace `REPLACE_WITH_REPO_DIR` with the absolute path to this repository.
   - Replace `REPLACE_WITH_BEARER_TOKEN` with your board's secret token.
   - If your board is not at `http://192.168.1.5:8090`, update `UNO_Q_RECEIVER_URL`.
2. Copy into LaunchAgents:
   ```bash
   cp mac-agent/launchd/com.stillloading.relay.plist ~/Library/LaunchAgents/
   ```
3. Load the daemon:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.stillloading.relay.plist
   ```
4. Check status:
   ```bash
   curl -s http://127.0.0.1:8765/health
   ```
