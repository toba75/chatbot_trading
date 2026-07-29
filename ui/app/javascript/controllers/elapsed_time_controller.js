import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { startedAt: String, endedAt: String }

  connect() {
    this.render()
    if (!this.hasEndedAtValue) this.timer = setInterval(() => this.render(), 1000)
  }

  disconnect() {
    clearInterval(this.timer)
  }

  render() {
    const end = this.hasEndedAtValue ? Date.parse(this.endedAtValue) : Date.now()
    const seconds = Math.max(0, Math.floor((end - Date.parse(this.startedAtValue)) / 1000))
    const days = Math.floor(seconds / 86400)
    const clock = [
      Math.floor(seconds % 86400 / 3600),
      Math.floor(seconds % 3600 / 60),
      seconds % 60
    ].map(value => String(value).padStart(2, "0")).join(":")

    this.element.textContent = days ? `${days} j ${clock}` : clock
  }
}
