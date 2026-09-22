import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false

  readonly property string pluginId: "io.github.jcarcinogen.blackdrop"
  property string activeOutput: ""
  readonly property string barPosition: shell && shell.bar && shell.bar.position
    ? String(shell.bar.position) : "top"
  readonly property var session: shell ? shell.serviceFor(pluginId) : null
  readonly property bool signalActive: session ? session.signalActive === true : false
  readonly property bool visualizerReady: session ? session.visualizerReady === true : false
  readonly property int beatRevision: session ? Number(session.beatRevision || 0) : 0
  readonly property int presetRevision: session ? Number(session.presetRevision || 0) : 0
  readonly property string currentPresetName: session ? String(session.currentPresetName || "") : ""
  readonly property bool silent: !signalActive || !visualizerReady
  readonly property bool setupRequired: session ? session.setupRequired === true : false
  readonly property var setupReasons: session && session.setupReasons ? session.setupReasons : []
  readonly property string setupCommand: session ? String(session.setupCommand || "") : ""
  readonly property bool setupAvailable: session ? session.setupAvailable === true : false
  readonly property bool copiedCommand: session ? session.copiedCommand === true : false
  property bool showPresetLogo: false
  property bool showPresetInfo: false

  component SetupButton: Rectangle {
    id: setupButton
    property string label: ""
    property bool emphasized: false
    signal triggered()

    width: parent ? parent.width : 240
    height: 40
    radius: Math.max(8, Style.cornerRadius)
    color: setupButton.emphasized
      ? Color.accent
      : Qt.rgba(1, 1, 1, setupMouse.containsMouse ? 0.16 : 0.09)

    Text {
      anchors.centerIn: parent
      text: setupButton.label
      textFormat: Text.PlainText
      color: setupButton.emphasized ? Color.background : Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.body
      font.weight: Font.DemiBold
    }

    MouseArea {
      id: setupMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: setupButton.triggered()
    }
  }

  function startService() {
    if (session && session.startSession) session.startSession(activeOutput)
    else if (opened) serviceRetry.restart()
  }

  function chooseOutput() {
    var monitor = Hyprland.focusedMonitor
    if (monitor && monitor.name) return String(monitor.name)
    var screens = Quickshell.screens || []
    return screens.length > 0 ? String(screens[0].name || "") : ""
  }

  function open(payloadJson) {
    activeOutput = chooseOutput()
    opened = true
    startService()
  }

  function close() {
    opened = false
    serviceRetry.stop()
    if (session && session.stopSession) session.stopSession()
  }

  // Hiding the plugin matters here: the overlay is a layer-shell Overlay, so it
  // always sits above ordinary windows. A setup terminal launched underneath it
  // would be invisible, so the overlay steps out of the way first.
  function dismiss() {
    close()
    if (shell && typeof shell.hide === "function") shell.hide(pluginId)
  }

  function toggle() {
    if (opened) close()
    else open("{}")
  }

  onSessionChanged: {
    if (opened) startService()
  }

  onPresetRevisionChanged: {
    if (opened && signalActive && currentPresetName) {
      showPresetInfo = true
      presetInfoTimer.restart()
    }
  }

  onBeatRevisionChanged: {
    if (opened && signalActive && visualizerReady) {
      showPresetLogo = true
      presetLogoTimer.restart()
    }
  }

  onSilentChanged: {
    if (silent) {
      showPresetLogo = false
      showPresetInfo = false
    }
  }

  Timer {
    id: presetInfoTimer
    interval: 2000
    repeat: false
    onTriggered: root.showPresetInfo = false
  }

  Timer {
    id: presetLogoTimer
    interval: 520
    repeat: false
    onTriggered: root.showPresetLogo = false
  }

  Timer {
    id: serviceRetry
    interval: 250
    repeat: false
    onTriggered: root.startService()
  }

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: panel
      required property var modelData

      screen: modelData
      visible: root.opened && modelData && modelData.name === root.activeOutput
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore

      WlrLayershell.namespace: "blackdrop-overlay"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

      IdleInhibitor {
        window: panel
        enabled: panel.visible
      }

      Shortcut {
        sequence: "Escape"
        enabled: panel.visible
        onActivated: root.close()
      }

      PanelKeyCatcher {
        id: keyCatcher
        anchors.fill: parent
        onCloseRequested: root.close()
        onMoveRequested: function(dx, dy) {
          if (!root.session) return
          if (dx < 0 && root.session.previousPreset) root.session.previousPreset()
          else if (dx > 0 && root.session.nextPreset) root.session.nextPreset()
          else if (dy < 0 && root.session.lockCurrentPreset) root.session.lockCurrentPreset()
          else if (dy > 0 && root.session.enableRandomPerSong) root.session.enableRandomPerSong()
        }

        Rectangle {
          anchors.fill: parent
          color: root.silent ? "#000000" : "transparent"
        }

        Rectangle {
          readonly property bool vertical: root.barPosition === "left" || root.barPosition === "right"
          anchors.top: root.barPosition === "top" ? parent.top : undefined
          anchors.bottom: root.barPosition === "bottom" ? parent.bottom : undefined
          anchors.left: root.barPosition === "left" || !vertical ? parent.left : undefined
          anchors.right: root.barPosition === "right" || !vertical ? parent.right : undefined
          width: vertical ? Style.bar.sizeVertical : parent.width
          height: vertical ? parent.height : Style.bar.sizeHorizontal
          color: "#000000"
          visible: !root.silent
        }

        Image {
          id: brandIcon
          visible: panel.visible && root.silent && !root.setupRequired
          source: Qt.resolvedUrl("assets/omarchy-logo.svg")
          sourceSize.width: 192
          sourceSize.height: 192
          width: Math.max(Style.font.displayLarge * 3, 72)
          height: width
          fillMode: Image.PreserveAspectFit
          smooth: true
          mipmap: true
          layer.enabled: true
          layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#9ece6a"
            shadowOpacity: 1.0
            shadowBlur: 1.0
            shadowScale: 1.32
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
          }
          x: panel.width * 0.12
          y: panel.height * 0.22

          SequentialAnimation on x {
            running: panel.visible && root.silent
            loops: Animation.Infinite
            NumberAnimation { from: panel.width * 0.12; to: panel.width * 0.82 - brandIcon.width; duration: 23000; easing.type: Easing.InOutSine }
            NumberAnimation { from: panel.width * 0.82 - brandIcon.width; to: panel.width * 0.12; duration: 19000; easing.type: Easing.InOutSine }
          }

          SequentialAnimation on y {
            running: panel.visible && root.silent
            loops: Animation.Infinite
            NumberAnimation { from: panel.height * 0.22; to: panel.height * 0.72 - brandIcon.height; duration: 17000; easing.type: Easing.InOutSine }
            NumberAnimation { from: panel.height * 0.72 - brandIcon.height; to: panel.height * 0.22; duration: 21000; easing.type: Easing.InOutSine }
          }
        }

        Image {
          id: presetLogo
          visible: root.showPresetLogo && !root.silent
          anchors.centerIn: parent
          source: Qt.resolvedUrl("assets/omarchy-logo.svg")
          sourceSize.width: 192
          sourceSize.height: 192
          width: Math.max(Style.font.displayLarge * 2.5, 64)
          height: width
          fillMode: Image.PreserveAspectFit
          smooth: true
          mipmap: true
          opacity: 0
          layer.enabled: true
          layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#9ece6a"
            shadowOpacity: 1.0
            shadowBlur: 1.0
            shadowScale: 1.35
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
          }

          SequentialAnimation on opacity {
            running: presetLogo.visible
            NumberAnimation { from: 0; to: 0.95; duration: 80; easing.type: Easing.OutCubic }
            PauseAnimation { duration: 220 }
            NumberAnimation { from: 0.95; to: 0; duration: 220; easing.type: Easing.InCubic }
          }
        }

        Rectangle {
          id: presetInfo
          visible: root.showPresetInfo && !root.silent
          anchors.horizontalCenter: parent.horizontalCenter
          anchors.bottom: parent.bottom
          anchors.bottomMargin: Math.max(Style.bar.sizeHorizontal * 2, 52)
          width: Math.min(parent.width * 0.9, Math.max(presetNameText.implicitWidth, presetHintText.implicitWidth) + 48)
          height: 76
          radius: Math.max(8, Style.cornerRadius)
          color: "#D9000000"
          border.width: 1
          border.color: "#9ece6a"
          z: 6

          Column {
            anchors.centerIn: parent
            spacing: 8

            Text {
              id: presetNameText
              anchors.horizontalCenter: parent.horizontalCenter
              width: presetInfo.width - 32
              horizontalAlignment: Text.AlignHCenter
              elide: Text.ElideRight
              text: root.currentPresetName
              textFormat: Text.PlainText
              color: "#9ece6a"
              font.family: Style.font.family
              font.pixelSize: Style.font.title
              font.weight: Font.DemiBold
            }

            Text {
              id: presetHintText
              anchors.horizontalCenter: parent.horizontalCenter
              width: presetInfo.width - 32
              horizontalAlignment: Text.AlignHCenter
              elide: Text.ElideRight
              text: "← Previous    → Next    ↑ Save    ↓ Random per song"
              textFormat: Text.PlainText
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.body
            }
          }
        }

        MouseArea {
          anchors.fill: parent
          visible: !root.setupRequired
          enabled: !root.setupRequired
          acceptedButtons: Qt.AllButtons
          hoverEnabled: true
          cursorShape: Qt.BlankCursor
          onPressed: function(mouse) { mouse.accepted = true }
          onReleased: function(mouse) { mouse.accepted = true }
          onWheel: function(wheel) { wheel.accepted = true }
        }

        // A marketplace install only clones the plugin. Rather than showing a
        // black screen with no explanation, say exactly what is missing and
        // offer the one visible step that fixes it.
        Rectangle {
          id: setupCard
          visible: root.setupRequired
          z: 20
          anchors.centerIn: parent
          width: Math.min(620, parent.width - 96)
          height: Math.min(setupColumn.implicitHeight + 56, parent.height - 96)
          radius: Math.max(10, Style.cornerRadius)
          color: "#F5000000"
          border.width: 1
          border.color: "#9ece6a"

          Column {
            id: setupColumn
            anchors {
              left: parent.left
              right: parent.right
              top: parent.top
              leftMargin: 28
              rightMargin: 28
              topMargin: 28
            }
            spacing: 14

            Text {
              width: parent.width
              text: "Blackdrop Setup Required"
              textFormat: Text.PlainText
              color: "#9ece6a"
              font.family: Style.font.family
              font.pixelSize: Style.font.title
              font.weight: Font.Bold
            }

            Text {
              width: parent.width
              text: "The plugin is installed. projectM and Blackdrop's one-time configuration are installed by you, in one visible step. Blackdrop never changes your configuration on its own."
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.body
            }

            Text {
              width: parent.width
              visible: root.setupReasons.length > 0
              text: "Still needed:\n" + root.setupReasons.map(function(item) { return "• " + item }).join("\n")
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
            }

            Rectangle {
              width: parent.width
              height: commandText.implicitHeight + 24
              radius: Math.max(6, Style.cornerRadius)
              color: Qt.rgba(1, 1, 1, 0.08)
              border.width: 1
              border.color: Qt.rgba(0.62, 0.81, 0.42, 0.5)

              Text {
                id: commandText
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                anchors.topMargin: 12
                text: root.setupCommand
                textFormat: Text.PlainText
                wrapMode: Text.WrapAnywhere
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }
            }

            Column {
              width: parent.width
              spacing: 8

              SetupButton {
                visible: root.setupAvailable
                label: "Open Setup Terminal"
                emphasized: true
                onTriggered: {
                  if (!root.session || !root.session.openSetupTerminal) return
                  // Only step aside once the terminal is actually on its way;
                  // a missing launcher keeps the card and its copy fallback up.
                  if (root.session.openSetupTerminal()) root.dismiss()
                }
              }

              SetupButton {
                label: root.copiedCommand ? "Copied to clipboard" : "Copy setup command"
                onTriggered: {
                  if (root.session && root.session.copySetupCommand) root.session.copySetupCommand()
                }
              }

              SetupButton {
                label: "Close"
                onTriggered: root.close()
              }
            }

            Text {
              width: parent.width
              text: root.setupAvailable
                ? "Setup adds the Super+Shift+B toggle and the projectM window rules to your Hyprland configuration and points projectM at Blackdrop's curated presets. The plugin's uninstall.sh reverses both. Press Escape to return to the desktop."
                : "Open a terminal and run the command above. It adds the Super+Shift+B toggle and the projectM window rules to your Hyprland configuration and points projectM at Blackdrop's curated presets. Press Escape to return to the desktop."
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              opacity: 0.75
            }
          }
        }
      }

      onVisibleChanged: {
        if (visible) Qt.callLater(function() { keyCatcher.forceActiveFocus() })
      }
    }
  }

  Component.onDestruction: {
    if (session && session.stopSession) session.stopSession()
  }
}
