# QUINEX GUI

## Using correct API and Bulkanalysis URLs

If the Quinex API and bulk analysis streamlit app aren't running on the same system, make sure to adapt the URLs in utility_functions.ts

## Starting the Development Server using Docker Compose

Starting the development server using Docker Compose is the recommended way to start the development server. This is because Docker Compose will automatically install the project dependencies and start the development server.

- ```bash
  ##Navigate to the root directory of the project in your terminal
  cd quinex_gui

  ##build the Docker image and start the containers
  docker-compose -f docker-compose-dev.yml up -d --build
  ##OR
  docker compose -f docker-compose-dev.yml up -d --build

  ##Check that the container is running
  docker ps
  ```

- The frontend server should now be running at `http://localhost:3003`.

## Starting the Development Server without Docker Compose

If you do not want to use Docker Compose, you can start the development server manually. This is not recommended, as you will have to manually install the project dependencies.

- ```bash
  ##Navigate to the root directory of the project in your terminal
  cd quinex_gui

  ##Install the project dependencies
  npm install

  ##Start the development server
  npm run dev
  ```

