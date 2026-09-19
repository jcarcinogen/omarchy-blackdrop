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
  property bool showPresetLogo: false
  property bool showPresetInfo: false

  function startService() {
    if (session && session.startSession) session.startSession()
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
          visible: panel.visible && root.silent
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
          acceptedButtons: Qt.AllButtons
          hoverEnabled: true
          cursorShape: Qt.BlankCursor
          onPressed: function(mouse) { mouse.accepted = true }
          onReleased: function(mouse) { mouse.accepted = true }
          onWheel: function(wheel) { wheel.accepted = true }
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
