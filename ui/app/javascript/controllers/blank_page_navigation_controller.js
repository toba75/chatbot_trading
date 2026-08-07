import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  show(event) {
    event.preventDefault()

    const panel = document.querySelector(event.currentTarget.getAttribute("href"))
    const pageInput = panel?.querySelector("[data-page-sync-target='page']")
    if (!pageInput) return

    pageInput.value = event.params.page
    pageInput.dispatchEvent(new Event("change", { bubbles: true }))
    panel.querySelector("[data-page-sync-target='viewer']")?.scrollIntoView({ block: "start" })
  }
}
