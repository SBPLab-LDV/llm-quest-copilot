import pandas as pd
from markitdown import MarkItDown

def read_excel_file(file_path):
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        # Display basic information about the DataFrame
        print("\nDataFrame Info:")
        print(df.info())
        
        # Convert DataFrame to dictionary
        # Method 1: Records format (list of dictionaries)
        records_dict = df.to_dict('records')
        
        # Method 2: Dictionary format (columns as keys)
        column_dict = df.to_dict()
        
        print("\nDictionary format (first record):")
        print(records_dict[0])
        
        return {
            'dataframe': df,
            'records': records_dict,
            'columns': column_dict
        }
    except Exception as e:
        print(f"Error reading Excel file: {str(e)}")
        return None

def convert_to_markdown(file_path):
    try:
        # Initialize MarkItDown
        md = MarkItDown()
        
        # Convert Excel to Markdown
        result = md.convert(file_path)
        
        # Save markdown content to file
        output_file = file_path.rsplit('.', 1)[0] + '.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.text_content)
            
        print(f"\nMarkdown file created: {output_file}")
        return result.text_content
    except Exception as e:
        print(f"Error converting to markdown: {str(e)}")
        return None

if __name__ == "__main__":
    excel_file_path = "口腔癌病人Q&A_關鍵字整理_20241209.xlsx"
    
    # Convert to markdown
    markdown_content = convert_to_markdown(excel_file_path)
    if markdown_content:
        print("\nPreview of markdown content:")
        print(markdown_content[:500] + "...")  # Preview first 500 characters
    
    # Original Excel reading functionality
    result = read_excel_file(excel_file_path)
    
    if result:
        # Access different formats
        df = result['dataframe']
        records = result['records']
        columns = result['columns']
