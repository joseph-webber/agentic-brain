# SPDX-License-Identifier: Apache-2.0

"""Tests for image-oriented office document structures."""

from __future__ import annotations


def test_image_preserves_binary_data_and_mime_type(sample_image) -> None:
    assert sample_image.data.startswith(b"\x89PNG")
    assert sample_image.mime_type == "image/png"


def test_image_supports_dimensions_and_titles(office_modules) -> None:
    image = office_modules.models.Image(
        data=b"img",
        mime_type="image/jpeg",
        width=320.0,
        height=240.0,
        title="Thumbnail",
    )
    assert image.width == 320.0
    assert image.height == 240.0
    assert image.title == "Thumbnail"


def test_image_position_maps_are_isolated(office_modules) -> None:
    first = office_modules.models.Image(data=b"a", mime_type="image/png")
    second = office_modules.models.Image(data=b"b", mime_type="image/png")
    first.position["x"] = 1.0
    assert second.position == {}


def test_image_properties_maps_are_isolated(office_modules) -> None:
    first = office_modules.models.Image(data=b"a", mime_type="image/png")
    second = office_modules.models.Image(data=b"b", mime_type="image/png")
    first.properties["decorative"] = True
    assert second.properties == {}


def test_slide_can_hold_multiple_images(office_modules, sample_image) -> None:
    second = office_modules.models.Image(data=b"img2", mime_type="image/jpeg")
    slide = office_modules.models.Slide(images=[sample_image, second])
    assert len(slide.images) == 2


def test_document_content_can_collect_images(office_modules, sample_image) -> None:
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.PPTX,
        images=[sample_image],
        resources={"image1.png": sample_image.data},
    )
    assert document.images[0].alternate_text == "Quarterly revenue chart"
    assert document.resources["image1.png"] == sample_image.data


def test_image_anchor_paragraph_supports_inline_placement(sample_image) -> None:
    assert sample_image.anchor_paragraph == "p-1"


def test_slide_background_and_images_are_independent(
    office_modules, sample_image
) -> None:
    slide = office_modules.models.Slide(images=[sample_image], background="#112233")
    assert slide.background == "#112233"
    assert slide.images[0].description == "Accessible chart image"


def test_shape_can_embed_text_alongside_images(
    office_modules, sample_paragraph
) -> None:
    shape = office_modules.models.Shape(
        shape_type="callout",
        path=[{"x": 0.0, "y": 0.0}],
        text=sample_paragraph,
    )
    assert shape.text is sample_paragraph


def test_chart_and_image_can_coexist_on_slide(
    office_modules, sample_image, sample_paragraph
) -> None:
    chart = office_modules.models.Chart(chart_type="line", title="Trend")
    slide = office_modules.models.Slide(
        title=sample_paragraph,
        images=[sample_image],
        charts=[chart],
    )
    assert slide.charts[0].title == "Trend"
    assert slide.images[0].title == "Chart"
