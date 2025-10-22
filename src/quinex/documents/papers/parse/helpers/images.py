import io
import warnings

try:
    import pymupdf as fitz
except ImportError:
    print("pymupdf not installed. Please install it with 'pip install pymupdf' if you want to use it to detect figures and tables with Grobid.")
    fitz = None    

try:
    from papermage.predictors import LPEffDetPubLayNetBlockPredictor
    from papermage.parsers.pdfplumber_parser import PDFPlumberParser
    from papermage.rasterizers.rasterizer import PDF2ImageRasterizer

    parser = PDFPlumberParser()
    rasterizer = PDF2ImageRasterizer()
    publaynet_block_predictor = LPEffDetPubLayNetBlockPredictor.from_pretrained()
    
except ImportError:
    print("papermage not installed. Please install it with 'pip install papermage' if you want to use it to detect figures and tables with papermage.")
    parser = None
    rasterizer = None
    publaynet_block_predictor = None
    


def extract_figures_and_tables(paper, pdf_path, images_dir):
    doc = parser.parse(input_pdf_path=pdf_path)
    images = rasterizer.rasterize(input_pdf_path=pdf_path, dpi=300)
    doc.annotate_images(images=list(images))
    rasterizer.attach_images(images=images, doc=doc)
        
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        blocks = publaynet_block_predictor.predict(doc=doc)
        
    # Save figures and tables.
    for i, block in enumerate(blocks):
        if block.metadata.type in ["Figure", "Table"]:
            box = block.boxes[0]
            serialized_image, figure_box_xy = get_serialized_image_from_box(box, doc.images)
            key = "figures" if block.metadata.type == "Figure" else "tables"
            # Adding {"bytes": serialized_image} to directory results in very large files.
            image_path = images_dir / f"{i}.png"
            paper[key].append({"coordinates": figure_box_xy, "link": image_path})

            # Save the image to a file.
            with open(image_path, "wb") as f:
                f.write(serialized_image)


def get_serialized_image_from_box(figure_box, page_images):        
    
    # Crop page image to box.
    figure_page_id = figure_box.page
    page_image = page_images[figure_page_id]
    page_w, page_h = page_image.pilimage.size
    figure_box_xy = figure_box.to_absolute(page_width=page_w, page_height=page_h).xy_coordinates
    figure = page_image._pilimage.crop(figure_box_xy)

    # Serialize image.
    serialized_figure = io.BytesIO()
    figure.save(serialized_figure, format="PNG")
    serialized_figure = str(serialized_figure.getvalue())

    return serialized_figure, figure_box_xy


def save_grobid_fig_tab_eq_as_image(paper, pdf_path, images_dir, dpi=300):

    filename = pdf_path.name.removesuffix(".pdf")
                    
    # Using PyMuPDF because its said to be faster than pdfplumber and I didn't 
    # had admin rights to install ImageMagick when writing this code.
    pdf_obj = fitz.open(pdf_path)

    def parser_bbox_coordinate_str(bbox_str):    
        """Parses a bbox coordinate string from GROBID to a tuple of integers and floats."""
        positions = bbox_str.split(";")
        bbox = []
        for position_str in positions:
            coords = position_str.split(",")        
            p = int(coords[0])   # page number
            x = float(coords[1]) # x-axis coordinate of the upper-left point
            y = float(coords[2]) # y-axis coordinate of the upper-left point
            w = float(coords[3]) # width 
            h = float(coords[4]) # height
            bbox.append([p, x, y, w, h])

        # TODO: Create an issue to swap width and height in Grobid documentation
        # at https://grobid.readthedocs.io/en/latest/Coordinates-in-PDF/.

        return bbox

    def bbox_to_crop(bbox):
        """Converts a list of bounding boxes to a cropbox by taking the union of all bounding boxes."""
        
        # Upper-left point of the cropbox.
        x0 = min([coords[1] for coords in bbox])
        y0 = min([coords[2] for coords in bbox])

        # Bottom-right point of the cropbox.
        x1 = max([coords[1] + coords[3] for coords in bbox])
        y1 = max([coords[2] + coords[4] for coords in bbox])
        
        crop = fitz.Rect(x0, y0, x1, y1)

        return crop

    for ref_key, ref in paper["pdf_parse"]["ref_entries"].items():                           

        # TODO: Handle equations just like figures and tables.                        
        
        # Get bounding boxes for current reference.
        # Note: A single reference may have multiple bounding boxes.
        bbox = parser_bbox_coordinate_str(ref["coords"])
        
        # Check if all p values are the same.    
        page_number = [coords[0] for coords in bbox]
        if len(set(page_number)) != 1:
            # TODO: Handle bounding boxes that span multiple pages.
            #raise NotImplementedError("Bounding box spans multiple pages.")
            continue
        else:
            # Note: In PyMuPDF and pdfplumber page object page numbers start from 0, 
            # but in PDF world and Grobid page numbers start from 1.
            page_number  = page_number[0] - 1 

        # Copy the page to end of PDF to leave the original page intact.
        pdf_obj.copy_page(page_number)    
        page = pdf_obj[-1]

        # Crop the page to the bounding box.    
        crop = bbox_to_crop(bbox)
        try:
            page.set_cropbox(crop)
        except ValueError as e:
            print(f'Failed to save table or figure reference {ref_key} for {paper["paper_id"]}.')
            continue                                                      
    
        # Save the page as an image.
        image = page.get_pixmap(dpi=dpi)
        image.save(images_dir / f"{ref_key}.png")