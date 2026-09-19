import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.jcarcinogen.blackdrop"

  readonly property bool opened: bar && bar.shell ? bar.shell.isPluginOpen(moduleName) : false

  function open() {
    if (bar && bar.shell) bar.shell.summon(moduleName, "{}")
  }

  function close() {
    if (bar && bar.shell) bar.shell.hide(moduleName)
  }

  function toggle() {
    if (bar && bar.shell) bar.shell.toggle(moduleName, "{}")
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    fontFamily: Style.font.family
    horizontalMargin: Style.space(7)
    tooltipText: "Blackdrop — fullscreen music visualization"

    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton) root.toggle()
    }
  }
}
