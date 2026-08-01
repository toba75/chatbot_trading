import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["frame"]
  static values = { url: String }

  connect() {
    this.wasConnected = false
    this.observer = new MutationObserver(() => this.reconcileIfConnected())
    this.observer.observe(this.element, {
      attributes: true,
      attributeFilter: ["connected"],
      childList: true,
      subtree: true
    })
    this.reconcileIfConnected()
  }

  disconnect() {
    this.observer.disconnect()
  }

  reconcileIfConnected() {
    const source = this.element.querySelector("turbo-cable-stream-source")
    if (!source) return

    const connected = source.hasAttribute("connected")
    if (connected && !this.wasConnected) {
      this.frameTarget.hasAttribute("src") ? this.frameTarget.reload() : this.frameTarget.setAttribute("src", this.urlValue)
    }
    this.wasConnected = connected
  }
}
