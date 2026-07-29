import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["frame"]
  static values = { url: String }

  connect() {
    this.source = this.element.querySelector("turbo-cable-stream-source")
    this.wasConnected = false
    this.observer = new MutationObserver(() => this.reconcileIfConnected())
    this.observer.observe(this.source, { attributes: true, attributeFilter: ["connected"] })
    this.reconcileIfConnected()
  }

  disconnect() {
    this.observer.disconnect()
  }

  reconcileIfConnected() {
    const connected = this.source.hasAttribute("connected")
    if (connected && !this.wasConnected) {
      this.frameTarget.hasAttribute("src") ? this.frameTarget.reload() : this.frameTarget.setAttribute("src", this.urlValue)
    }
    this.wasConnected = connected
  }
}
