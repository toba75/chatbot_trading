import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["tab", "preview"]

  select(event) {
    this.activate(event.currentTarget)
  }

  navigate(event) {
    const tabs = this.tabTargets.filter(tab => !tab.hidden)
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
    destination.click()
  }

  activate(activeTab) {
    this.tabTargets.forEach(tab => {
      const selected = tab === activeTab
      tab.classList.toggle("active", selected)
      tab.setAttribute("aria-selected", selected)
      tab.tabIndex = selected ? 0 : -1
    })
    this.previewTarget.title = activeTab.dataset.previewTitle
    this.previewTarget.setAttribute("aria-labelledby", activeTab.id)
  }
}
