import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["tab", "panel"]

  connect() {
    const selected = this.tabTargets.find(tab => tab.getAttribute("aria-selected") === "true")
    this.activate(selected || this.tabTargets[0], false)
  }

  select(event) {
    event.preventDefault()
    this.activate(event.currentTarget)
  }

  navigate(event) {
    const tabs = this.tabTargets
    const current = tabs.indexOf(event.currentTarget)
    const destinations = {
      ArrowLeft: (current - 1 + tabs.length) % tabs.length,
      ArrowRight: (current + 1) % tabs.length,
      Home: 0,
      End: tabs.length - 1
    }
    if (!(event.key in destinations)) return

    event.preventDefault()
    const destination = tabs[destinations[event.key]]
    destination.focus()
    this.activate(destination)
  }

  activate(activeTab, announce = true) {
    if (!activeTab) return

    const panelId = activeTab.getAttribute("aria-controls")
    this.tabTargets.forEach(tab => {
      const selected = tab === activeTab
      tab.classList.toggle("active", selected)
      tab.setAttribute("aria-selected", selected)
      tab.tabIndex = selected ? 0 : -1
    })
    this.panelTargets.forEach(panel => {
      panel.hidden = panel.id !== panelId
    })

    if (announce) {
      window.dispatchEvent(new CustomEvent("panel-tabs:shown", { detail: { panelId } }))
    }
  }
}
