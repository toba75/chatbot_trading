Rails.application.routes.draw do
  root "documents#new"
  resources :documents, only: %i[index create show] do
    member do
      get :html_preview
      get :page_html_preview
      get :derived_html_preview
      get :markdown_preview
      get :docling_preview
      get :docling_page_preview
      post "retry", to: "documents#retry_conversion", as: :retry
      post :retry_math_qualification
    end
  end
  get "up" => "rails/health#show", as: :rails_health_check
end
