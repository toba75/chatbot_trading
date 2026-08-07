Rails.application.routes.draw do
  root "documents#new"
  resources :documents, only: %i[index create show destroy] do
    collection do
      get :trash
    end
    member do
      get :html_preview
      get :page_html_preview
      get :derived_html_preview
      get :markdown_preview
      get :docling_preview
      get :docling_page_preview
      post "retry", to: "documents#retry_conversion", as: :retry
      post :retry_math_qualification
      post :enrich_metadata
      post :confirm_metadata
      post :reject_metadata
      post :restore
    end
  end
  get "up" => "rails/health#show", as: :rails_health_check
  if Rails.env.test?
    get "system-test/environment" => proc {
      SolidCable::Message.connection.select_value("SELECT 1")
      identity = [
        Rails.env,
        ActiveRecord::Base.connection_db_config.database,
        SolidCable::Message.connection_db_config.database,
        ActiveStorage::Blob.service.root
      ].join("|")
      [ 200, { "content-type" => "text/plain; charset=utf-8" }, [ identity ] ]
    }, as: :system_test_environment
  end
end
