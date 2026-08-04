import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { url: String, label: String, corrected: Boolean }

  connect() {
    window.dispatchEvent(new CustomEvent("page-html:available", {
      detail: { url: this.urlValue, label: this.labelValue, corrected: this.correctedValue }
    }))
  }
}
