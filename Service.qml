import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons

Item {
  id: root

  readonly property string pluginId: "io.github.jcarcinogen.blackdrop"
  readonly property string pluginDir: Quickshell.env("HOME") + "/.config/omarchy/plugins/" + pluginId

  property bool sessionEnabled: false
  property bool signalActive: false
  property bool visualizerReady: false
  property bool presetLocked: false
  property int presetRevision: 0
  property int beatRevision: 0
  property int beatFlashRemaining: 0
  property double nextLogoAtMs: 0
  property string sinkMonitor: ""
  property string targetOutput: ""
  property string lastError: ""
  readonly property var presetNames: [
    "EoS - glowsticks v2 05 and proton lights (Krash beat code)",
    "EoS - repeater 13 - definitive fast",
    "Idiot & Rovastar - Harlequin Trapped In Marphet's Vortex 2",
    "Mstress - Acoustic Nerve Impulses",
    "Rovastar & Krash - Cerebral Demons (Beat Pulse Mix)",
    "Rovastar - Harlequin's Dynamic Fractal 3",
    "Rovastar - Inner Thoughts (Frantic Thoughts Mix)",
    "Rovastar - Jester's Awakening",
    "Rovastar - Solarized Space (Space DNA Mix)",
    "Rovastar - Tripmaker (Space Trip Mix)",
    "Rovastar - VooV's Movement (After Dark Mix)",
    "shifter - liquid circuitry"
  ]
  property int currentPresetIndex: -1
  readonly property string currentPresetName: currentPresetIndex >= 0 && currentPresetIndex < presetNames.length
    ? presetNames[currentPresetIndex] : ""

  readonly property bool visualizerRunning: visualizerProc.running
  readonly property bool monitorRunning: monitorProc.running

  // Read-only readiness probe (scripts/status.py). A marketplace install only
  // clones this plugin: the projectM packages and Blackdrop's reversible local
  // configuration are a separate, visible user action, so report that state
  // instead of failing silently behind a black screen.
  property var statusPayload: ({})
  property bool statusKnown: false
  readonly property bool ready: statusPayload.ready === true
  readonly property bool setupRequired: statusKnown && !ready
  readonly property var setupReasons: statusPayload.reasons ? statusPayload.reasons : []
  readonly property string setupCommand: String(statusPayload.setup_command || "")
  readonly property bool setupAvailable: statusPayload.setup_available === true
  readonly property string packageStep: String(statusPayload.package_step || "")
  readonly property string pluginVersion: String(statusPayload.version || "")
  property bool setupLaunched: false
  property bool copiedCommand: false

  function scheduleNextBeatLogo() {
    // Randomize within 3.5–4.5 minutes so it feels occasional, not clocked.
    nextLogoAtMs = Date.now() + 210000 + Math.floor(Math.random() * 60001)
  }

  function startSession(outputName) {
    targetOutput = String(outputName || "")
    sessionEnabled = true
    lastError = ""
    setupLaunched = false
    if (nextLogoAtMs <= Date.now()) scheduleNextBeatLogo()
    refreshStatus()
  }

  function refreshStatus() {
    if (statusProc.running) return
    statusProc.running = true
  }

  function applyStatus(exitCode) {
    if (exitCode !== 0) {
      statusKnown = true
      statusPayload = ({ ready: false, reasons: ["Blackdrop could not read its setup status on this machine."] })
      if (sessionEnabled) statusTimer.restart()
      return
    }
    try {
      var parsed = JSON.parse(String(statusOut.text || ""))
      if (!parsed || parsed.schema !== 1 || typeof parsed.checks !== "object"
          || parsed.checks === null || !Array.isArray(parsed.reasons)) {
        statusKnown = true
        statusPayload = ({ ready: false, reasons: ["Blackdrop's setup probe returned an unsupported schema."] })
        if (sessionEnabled) statusTimer.restart()
        return
      }
      statusPayload = parsed
      statusKnown = true
      if (parsed.ready === true) {
        lastError = ""
        statusTimer.stop()
        if (!monitorProc.running) monitorProc.running = true
      } else if (sessionEnabled) {
        statusTimer.restart()
      }
    } catch (error) {
      statusKnown = true
      statusPayload = ({ ready: false, reasons: ["Blackdrop's setup probe returned invalid JSON."] })
      if (sessionEnabled) statusTimer.restart()
    }
  }

  function openSetupTerminal() {
    if (!setupAvailable || setupProcess.running) return false
    setupProcess.command = [
      "/usr/bin/omarchy-launch-floating-terminal-with-presentation",
      root.pluginDir + "/setup.sh"
    ]
    setupProcess.running = true
    setupLaunched = true
    return true
  }

  function copySetupCommand() {
    if (!setupCommand) return false
    Quickshell.execDetached(["bash", "-c", "printf %s " + Util.shellQuote(setupCommand) + " | wl-copy"])
    copiedCommand = true
    copiedReset.restart()
    return true
  }

  function stopSession() {
    sessionEnabled = false
    signalActive = false
    visualizerReady = false
    presetLocked = false
    currentPresetIndex = -1
    targetOutput = ""
    beatFlashRemaining = 0
    nextLogoAtMs = 0
    readyTimer.stop()
    stopVisualizerTimer.stop()
    monitorRestartTimer.stop()
    visualizerRestartTimer.stop()
    statusTimer.stop()
    copiedReset.stop()
    if (visualizerProc.running) visualizerProc.running = false
    if (monitorProc.running) monitorProc.running = false
  }

  function chooseRandomPresetIndex() {
    if (presetNames.length < 2) return 0
    var next = Math.floor(Math.random() * presetNames.length)
    if (next === currentPresetIndex) next = (next + 1) % presetNames.length
    return next
  }

  function navigationKeys(targetIndex) {
    if (currentPresetIndex < 0) return []
    var forward = (targetIndex - currentPresetIndex + presetNames.length) % presetNames.length
    var backward = (currentPresetIndex - targetIndex + presetNames.length) % presetNames.length
    var key = forward <= backward ? "n" : "p"
    var count = Math.min(forward, backward)
    var keys = []
    for (var i = 0; i < count; i++) keys.push(key)
    return keys
  }

  function startVisualizer() {
    if (!sessionEnabled || !signalActive || visualizerProc.running) return
    if (currentPresetIndex < 0 || !presetLocked) currentPresetIndex = chooseRandomPresetIndex()
    visualizerProc.command = [root.pluginDir + "/scripts/run-projectm.sh", String(currentPresetIndex), targetOutput]
    presetRevision++
    visualizerProc.running = true
  }

  function stopVisualizer() {
    visualizerReady = false
    readyTimer.stop()
    if (visualizerProc.running) visualizerProc.running = false
  }

  function sendPresetKeys(keys) {
    if (!sessionEnabled || !visualizerProc.running || presetKeyProc.running) return false
    if (!Array.isArray(keys) || keys.length === 0) return false
    for (var i = 0; i < keys.length; i++) {
      if (["n", "p", "l"].indexOf(keys[i]) === -1) return false
    }
    presetKeyProc.command = [root.pluginDir + "/scripts/projectm-key.py"].concat(keys)
    presetKeyProc.running = true
    return true
  }

  function movePreset(delta) {
    if (currentPresetIndex < 0 || presetNames.length === 0) return
    var target = (currentPresetIndex + delta + presetNames.length) % presetNames.length
    if (sendPresetKeys([delta > 0 ? "n" : "p"])) {
      currentPresetIndex = target
      presetRevision++
    }
  }

  function nextPreset() { movePreset(1) }
  function previousPreset() { movePreset(-1) }

  function chooseRandomPreset() {
    if (currentPresetIndex < 0 || presetNames.length === 0) return
    var target = chooseRandomPresetIndex()
    var keys = navigationKeys(target)
    if (keys.length > 0 && sendPresetKeys(keys)) {
      currentPresetIndex = target
      presetRevision++
    }
  }

  function lockCurrentPreset() {
    if (presetLocked) return
    if (sendPresetKeys(["l"])) presetLocked = true
  }

  function enableRandomPerSong() {
    if (!visualizerProc.running) {
      presetLocked = false
      currentPresetIndex = -1
      return
    }
    var target = chooseRandomPresetIndex()
    var keys = navigationKeys(target)
    if (presetLocked) keys.unshift("l")
    if (keys.length > 0 && sendPresetKeys(keys)) {
      presetLocked = false
      currentPresetIndex = target
      presetRevision++
    }
  }

  function handleMonitorLine(data) {
    var line = String(data || "").trim()
    if (!line) return

    if (line.indexOf("sink:") === 0) {
      var nextSink = line.slice(5)
      if (nextSink !== sinkMonitor) {
        sinkMonitor = nextSink
        presetLocked = false
        if (visualizerProc.running) {
          visualizerReady = false
          visualizerProc.running = false
          if (sessionEnabled && signalActive) visualizerRestartTimer.restart()
        }
      }
      return
    }

    if (line === "active") {
      var wasActive = signalActive
      var visualizerWasRunning = visualizerProc.running
      signalActive = true
      stopVisualizerTimer.stop()
      if (visualizerWasRunning) {
        visualizerReady = true
        if (!wasActive && !presetLocked) chooseRandomPreset()
      } else {
        startVisualizer()
      }
    } else if (line === "silent") {
      signalActive = false
      visualizerReady = false
      readyTimer.stop()
      stopVisualizerTimer.restart()
    } else if (line === "beat") {
      if (!signalActive) return
      if (beatFlashRemaining > 0) {
        beatRevision++
        beatFlashRemaining--
        if (beatFlashRemaining === 0) scheduleNextBeatLogo()
      } else if (Date.now() >= nextLogoAtMs) {
        beatRevision++
        beatFlashRemaining = 2
      }
    } else if (line.indexOf("error:") === 0) {
      lastError = line.slice(6)
    }
  }

  Process {
    id: monitorProc
    command: [root.pluginDir + "/scripts/audio-watch.py"]
    stdout: SplitParser {
      onRead: function(data) { root.handleMonitorLine(data) }
    }
    onExited: function(exitCode) {
      root.signalActive = false
      root.visualizerReady = false
      if (root.sessionEnabled) {
        root.lastError = "audio monitor exited " + exitCode
        monitorRestartTimer.restart()
      }
    }
  }

  Process {
    id: visualizerProc
    command: [root.pluginDir + "/scripts/run-projectm.sh"]
    stderr: SplitParser {
      onRead: function(data) {
        var line = String(data || "").trim()
        if (line.indexOf("Blackdrop:") === 0) root.lastError = line
      }
    }
    onRunningChanged: {
      if (running) readyTimer.restart()
      else {
        readyTimer.stop()
        root.visualizerReady = false
      }
    }
    onExited: function(exitCode) {
      if (root.sessionEnabled && root.signalActive) {
        root.lastError = "projectM exited " + exitCode
        visualizerRestartTimer.restart()
      }
    }
  }

  Process {
    id: presetKeyProc
    onExited: function(exitCode) {
      if (exitCode !== 0) root.lastError = "preset navigation exited " + exitCode
    }
  }

  Timer {
    id: readyTimer
    interval: 1200
    repeat: false
    onTriggered: root.visualizerReady = visualizerProc.running && root.sessionEnabled && root.signalActive
  }

  Timer {
    id: stopVisualizerTimer
    interval: 1000
    repeat: false
    onTriggered: {
      if (!root.presetLocked) root.stopVisualizer()
    }
  }

  Timer {
    id: monitorRestartTimer
    interval: 1500
    repeat: false
    onTriggered: {
      if (root.sessionEnabled && !monitorProc.running) monitorProc.running = true
    }
  }

  Timer {
    id: visualizerRestartTimer
    interval: 800
    repeat: false
    onTriggered: root.startVisualizer()
  }

  Process {
    id: setupProcess
    command: [root.pluginDir + "/setup.sh"]
    onExited: function(exitCode) {
      root.lastError = exitCode === 0 ? "" : "setup exited " + exitCode
      statusRetry.restart()
    }
  }

  Process {
    id: statusProc
    command: ["python3", root.pluginDir + "/scripts/status.py", "--json"]
    stdout: StdioCollector {
      id: statusOut
      waitForEnd: true
    }
    stderr: StdioCollector {
      waitForEnd: true
    }
    onExited: function(exitCode) { root.applyStatus(exitCode) }
  }

  Timer {
    id: statusTimer
    interval: 3000
    repeat: true
    onTriggered: root.refreshStatus()
  }

  Timer {
    id: statusRetry
    interval: 800
    repeat: false
    onTriggered: root.refreshStatus()
  }

  Timer {
    id: copiedReset
    interval: 2000
    repeat: false
    onTriggered: root.copiedCommand = false
  }

  IpcHandler {
    target: root.pluginId

    function status(): string {
      return JSON.stringify({
        sessionEnabled: root.sessionEnabled,
        ready: root.ready,
        setupRequired: root.setupRequired,
        setupReasons: root.setupReasons,
        setupCommand: root.setupCommand,
        setupAvailable: root.setupAvailable,
        signalActive: root.signalActive,
        sinkMonitor: root.sinkMonitor,
        monitorRunning: root.monitorRunning,
        visualizerRunning: root.visualizerRunning,
        visualizerReady: root.visualizerReady,
        presetLocked: root.presetLocked,
        randomPerSong: !root.presetLocked,
        currentPresetIndex: root.currentPresetIndex,
        currentPresetName: root.currentPresetName,
        presetRevision: root.presetRevision,
        beatRevision: root.beatRevision,
        beatFlashRemaining: root.beatFlashRemaining,
        nextLogoAtMs: root.nextLogoAtMs,
        lastError: root.lastError
      })
    }

    function setupStatus(): string {
      root.refreshStatus()
      return JSON.stringify(root.statusPayload)
    }

    function openSetup(): string {
      return root.openSetupTerminal() ? "ok" : "unavailable"
    }

    function start(): string {
      root.startSession()
      return "ok"
    }

    function nextPreset(): string {
      root.nextPreset()
      return "ok"
    }

    function previousPreset(): string {
      root.previousPreset()
      return "ok"
    }

    function lockPreset(): string {
      root.lockCurrentPreset()
      return "ok"
    }

    function randomPreset(): string {
      root.enableRandomPerSong()
      return "ok"
    }

    function stop(): string {
      root.stopSession()
      return "ok"
    }
  }

  Component.onDestruction: stopSession()
}
