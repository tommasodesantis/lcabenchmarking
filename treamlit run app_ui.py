[1mdiff --git a/analyzer.py b/analyzer.py[m
[1mindex 495f112..6bcabd7 100644[m
[1m--- a/analyzer.py[m
[1m+++ b/analyzer.py[m
[36m@@ -45,42 +45,21 @@[m [mclass LCAAnalyzer:[m
                 }[m
             )[m
             [m
[31m-            # Log detailed response information[m
[31m-            logger.info("=== Response Details ===")[m
[31m-            logger.info(f"Response type: {type(response)}")[m
[31m-            logger.info(f"Response dir: {dir(response)}")[m
[31m-            logger.info(f"Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")[m
[32m+[m[32m            # Access chunk_search_results through the results attribute[m
[32m+[m[32m            chunk_results = response.results.chunk_search_results[m
             [m
[31m-            # Log results attribute if it exists[m
[31m-            if hasattr(response, 'results'):[m
[31m-                logger.info("=== Results Details ===")[m
[31m-                logger.info(f"Results type: {type(response.results)}")[m
[31m-                logger.info(f"Results dir: {dir(response.results)}")[m
[31m-                logger.info(f"Results attributes: {[attr for attr in dir(response.results) if not attr.startswith('_')]}")[m
[31m-                [m
[31m-                # Log chunk_search_results if it exists[m
[31m-                if hasattr(response.results, 'chunk_search_results'):[m
[31m-                    logger.info("=== Chunk Search Results Details ===")[m
[31m-                    chunk_results = response.results.chunk_search_results[m
[31m-                    logger.info(f"chunk_search_results type: {type(chunk_results)}")[m
[31m-                    if chunk_results:[m
[31m-                        logger.info(f"First chunk type: {type(chunk_results[0])}")[m
[31m-                        logger.info(f"First chunk dir: {dir(chunk_results[0])}")[m
[31m-                        logger.info(f"First chunk attributes: {[attr for attr in dir(chunk_results[0]) if not attr.startswith('_')]}")[m
[31m-                        # Try to access common attributes[m
[31m-                        try:[m
[31m-                            logger.info(f"First chunk text: {chunk_results[0].text if hasattr(chunk_results[0], 'text') else 'No text attribute'}")[m
[31m-                            logger.info(f"First chunk score: {chunk_results[0].score if hasattr(chunk_results[0], 'score') else 'No score attribute'}")[m
[31m-                            logger.info(f"First chunk metadata: {chunk_results[0].metadata if hasattr(chunk_results[0], 'metadata') else 'No metadata attribute'}")[m
[31m-                        except Exception as attr_e:[m
[31m-                            logger.error(f"Error accessing chunk attributes: {str(attr_e)}")[m
[31m-                else:[m
[31m-                    logger.error("No chunk_search_results attribute found in results")[m
[31m-            else:[m
[31m-                logger.error("No results attribute found in response")[m
[32m+[m[32m            # Convert Pydantic models to dictionaries[m
[32m+[m[32m            chunks = [][m
[32m+[m[32m            for chunk in chunk_results:[m
[32m+[m[32m                chunk_dict = {[m
[32m+[m[32m                    "text": chunk.text,[m
[32m+[m[32m                    "score": chunk.score,[m
[32m+[m[32m                    "metadata": chunk.metadata[m
[32m+[m[32m                }[m
[32m+[m[32m                chunks.append(chunk_dict)[m
             [m
[31m-            # For now, just raise the error to see the logs[m
[31m-            raise TypeError(f"Logging response structure. Check logs for details.")[m
[32m+[m[32m            logger.info(f"Successfully retrieved {len(chunks)} chunks")[m
[32m+[m[32m            return chunks[m
             [m
         except Exception as e:[m
             logger.error(f"Error in get_chunks: {str(e)}", exc_info=True)[m
