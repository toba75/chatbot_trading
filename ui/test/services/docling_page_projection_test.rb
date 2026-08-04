require "test_helper"

class DoclingPageProjectionTest < ActiveSupport::TestCase
  test "conserve seulement la page et les contenus qui lui sont attribués" do
    source = {
      "schema_name" => "DoclingDocument",
      "version" => "1.8.0",
      "name" => "sample",
      "body" => { "children" => [ { "$ref" => "#/texts/0" }, { "$ref" => "#/texts/1" } ] },
      "texts" => [
        { "self_ref" => "#/texts/0", "text" => "page un", "prov" => [ { "page_no" => 1 } ] },
        { "self_ref" => "#/texts/1", "text" => "page deux", "prov" => [ { "page_no" => 2 } ] }
      ],
      "pictures" => [
        { "self_ref" => "#/pictures/0", "prov" => [ { "page_no" => 2 } ], "image" => { "uri" => "data:image/png;base64,page2" } }
      ],
      "tables" => [],
      "key_value_items" => [],
      "form_items" => [],
      "pages" => {
        "1" => { "page_no" => 1, "image" => { "uri" => "data:image/png;base64,page1" } },
        "2" => { "page_no" => 2, "image" => { "uri" => "data:image/png;base64,page2" } }
      }
    }

    links = [ { "id" => "pdf-source:2:4", "docling_ref" => "#/texts/1" } ]
    projection = project(source, page: 2, math_links: links)

    assert_equal "docling_page", projection.dig("_projection", "kind")
    assert_equal 2, projection.dig("_projection", "page_no")
    assert_equal "DoclingDocument", projection["schema_name"]
    assert_equal 2, projection.dig("page", "page_no")
    assert_equal links, projection.fetch("_math_links")
    assert_equal [ "page deux" ], projection.fetch("texts").pluck("text")
    assert_equal [ "#/pictures/0" ], projection.fetch("pictures").pluck("self_ref")
    assert_empty projection.fetch("tables")
    assert_not projection.key?("body")
    assert_not_includes JSON.generate(projection), "page un"
  end

  test "signale une page absente" do
    error = assert_raises(DoclingPageProjection::PageNotFound) do
      project({ "pages" => { "1" => { "page_no" => 1 } } }, page: 3)
    end

    assert_equal 3, error.page
  end

  private

  def project(source, page:, math_links: [])
    Tempfile.create([ "docling", ".json" ]) do |file|
      file.write(JSON.generate(source))
      file.rewind
      return DoclingPageProjection.call(file, page: page, math_links: math_links)
    end
  end
end
