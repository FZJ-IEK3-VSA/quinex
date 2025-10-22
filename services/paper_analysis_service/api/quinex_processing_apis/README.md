# Processing APIs
There are two APIs to process texts using Quinex: 
* `background_api` loads the models once and continously listens for request. 
* `on_demand_batch_processing_api` is assumed to run on the head node of a SLURM cluster. This API waits for incoming requests, and upon receiving a request, it creates SLURM jobs to process the request on compute nodes. Thus, it only consumes relevant compute resources on request but has a higher latency as the SLURM jobs must be allocated and the models have to be loaded into memory for each SLURM job.